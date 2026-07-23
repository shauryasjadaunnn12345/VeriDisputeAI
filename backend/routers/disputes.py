"""
disputes.py

Core dispute lifecycle endpoints: create a dispute, submit evidence (parsed
via the Mistral LLM), check status, resolve (the rule-engine + model +
explainability pipeline), and fetch the resulting decision.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Decision, Dispute, Evidence
from backend.models.schemas import (
    DecisionOut,
    DisputeCreate,
    DisputeOut,
    EvidenceCreate,
    EvidenceOut,
    StatusOut,
)
from backend.services import evidence_signals, llm_parser, ml_service, rule_engine

router = APIRouter(prefix="/disputes", tags=["disputes"])

# Confidence routing thresholds (percent).
AUTO_REJECT_BELOW = 20
AUTO_APPROVE_ABOVE = 85


@router.post("", response_model=DisputeOut)
def create_dispute(payload: DisputeCreate, db: Session = Depends(get_db)):
    if payload.reason_code not in rule_engine.REQUIRED_EVIDENCE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown reason_code '{payload.reason_code}'. "
                f"Expected one of {list(rule_engine.REQUIRED_EVIDENCE.keys())}"
            ),
        )

    dispute = Dispute(
        card_member_id=payload.card_member_id,
        merchant_id=payload.merchant_id,
        reason_code=payload.reason_code,
        amount=payload.amount,
        status="open",
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute


@router.post("/{dispute_id}/evidence", response_model=EvidenceOut)
def submit_evidence(dispute_id: int, payload: EvidenceCreate, db: Session = Depends(get_db)):
    dispute = db.get(Dispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found")

    try:
        parsed_fields = llm_parser.parse_evidence(payload.raw_text)
    except RuntimeError as e:
        # Mistral API not configured / reachable -- don't fail the whole
        # request, just store the evidence without parsed fields.
        parsed_fields = {"parse_error": True, "raw_response": str(e)}

    evidence = Evidence(
        dispute_id=dispute_id,
        submitted_by=payload.submitted_by,
        evidence_type=payload.evidence_type,
        raw_text=payload.raw_text,
        parsed_fields=parsed_fields,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


@router.get("/{dispute_id}/status", response_model=StatusOut)
def get_dispute_status(dispute_id: int, db: Session = Depends(get_db)):
    dispute = db.get(Dispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found")

    evidence_count = (
        db.query(Evidence).filter(Evidence.dispute_id == dispute_id).count()
    )
    return StatusOut(dispute_id=dispute_id, status=dispute.status, evidence_count=evidence_count)


def _build_feature_vector(
    db: Session, dispute: Dispute, evidence_list: List[Evidence], evidence_completeness_pct: float
) -> dict:
    """Reconstruct the model's raw feature vector from stored/parsed
    evidence, with sensible defaults for anything not yet captured.

    has_tracking: True only if at least one evidence item has a
    tracking_number that (a) passes a plausibility check -- rejects
    empty/placeholder/garbage values like "wrong", "123456", "n/a" via
    evidence_signals.is_plausible_tracking_number, including a check for
    "this tracking number is wrong" language elsewhere in the same
    evidence's raw_text -- and (b) isn't contradicted by a delivery_status
    that indicates the package was NOT actually delivered (e.g. "in
    transit", "lost", "returned to sender"). A tracking number that proves
    non-delivery supports the card member's case, not the merchant's, so
    it must not set has_tracking = True.

    has_signature_confirmation: prefers the LLM's explicit
    signature_confirmation field (from any submitter); if that field is
    null/missing (LLM not configured, parse failure, or field simply not
    extracted), falls back to keyword detection over that evidence's
    raw_text + delivery_status via evidence_signals.

    merchant_policy_compliance: same idea, but only evidence submitted by
    the merchant (submitted_by == "merchant") is considered, since this
    signal is specifically about the merchant's own conduct.
    """

    has_tracking = False
    has_signature_confirmation = False
    merchant_policy_compliance = False

    for ev in evidence_list:
        fields = ev.parsed_fields if isinstance(ev.parsed_fields, dict) else {}

        # --- Tracking: must be a plausible number AND not contradicted by
        # a "not actually delivered" status. ---
        tracking_number = fields.get("tracking_number")
        delivery_status = fields.get("delivery_status")
        if evidence_signals.is_plausible_tracking_number(tracking_number, ev.raw_text or ""):
            if evidence_signals.is_delivery_confirmed(delivery_status):
                has_tracking = True

        # --- Signature / delivery confirmation ---
        explicit_signature = fields.get("signature_confirmation")
        if explicit_signature is True:
            has_signature_confirmation = True
        elif explicit_signature is None:
            text_to_scan = " ".join(
                part for part in [ev.raw_text, delivery_status] if isinstance(part, str)
            )
            if evidence_signals.detect_signature_confirmation(text_to_scan):
                has_signature_confirmation = True
        # explicit_signature is False -> LLM found an explicit "no signature"
        # signal; treat as authoritative and don't fall back to keywords.

        # --- Merchant policy compliance (merchant-submitted evidence only) ---
        if ev.submitted_by == "merchant":
            explicit_compliance = fields.get("policy_compliance")
            if explicit_compliance is True:
                merchant_policy_compliance = True
            elif explicit_compliance is None:
                if evidence_signals.detect_policy_compliance(ev.raw_text or ""):
                    merchant_policy_compliance = True

    # We do have real history for this: count the card member's other disputes.
    dispute_history_count = (
        db.query(Dispute)
        .filter(Dispute.card_member_id == dispute.card_member_id, Dispute.id != dispute.id)
        .count()
    )
    dispute_history_count = min(dispute_history_count, 10)

    # Not yet tracked end-to-end (no merchant response event in the DB yet)
    # -- sensible neutral default.
    merchant_response_time_hours = 48.0

    return {
        "reason_code": dispute.reason_code,
        "has_tracking": has_tracking,
        "has_signature_confirmation": has_signature_confirmation,
        "merchant_response_time_hours": merchant_response_time_hours,
        "merchant_policy_compliance": merchant_policy_compliance,
        "card_member_dispute_history_count": dispute_history_count,
        "evidence_completeness_pct": evidence_completeness_pct,
    }


@router.post("/{dispute_id}/resolve", response_model=DecisionOut)
def resolve_dispute(dispute_id: int, db: Session = Depends(get_db)):
    dispute = db.get(Dispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found")

    # 1. Load all evidence, aggregate evidence types.
    evidence_list = db.query(Evidence).filter(Evidence.dispute_id == dispute_id).all()
    evidence_types = [ev.evidence_type for ev in evidence_list]

    # 2. Evidence completeness via the rule engine.
    completeness = rule_engine.evidence_completeness(dispute.reason_code, evidence_types)
    completeness_pct = completeness["completeness_pct"]

    # 3. Build the feature vector.
    feature_vector = _build_feature_vector(db, dispute, evidence_list, completeness_pct)

    # 4. Predict outcome + probability.
    prediction = ml_service.predict_outcome(feature_vector)
    outcome = prediction["outcome"]
    confidence_pct = prediction["confidence_pct"]

    # 5. Explainability.
    shap_explanation = ml_service.get_shap_explanation(feature_vector)
    counterfactual = ml_service.get_counterfactual(feature_vector)

    if counterfactual["changed"]:
        counterfactual_text = (
            f"Flipping '{counterfactual['feature_flipped']}' from "
            f"{counterfactual['flipped_from']} to {counterfactual['flipped_to']} "
            f"would change the outcome to '{counterfactual['new_outcome']}'."
        )
    else:
        counterfactual_text = "No single feature flip changes the predicted outcome."

    top_feat_summary = "; ".join(
        f"{f['feature']} ({f['direction']})" for f in shap_explanation["top_features"]
    )
    missing_str = ", ".join(completeness["missing"]) if completeness["missing"] else "none"
    reasoning_text = (
        f"Predicted '{outcome}' with {confidence_pct}% confidence. "
        f"Evidence completeness: {completeness_pct}% (missing: {missing_str}). "
        f"Top factors: {top_feat_summary}."
    )

    # 6. Confidence routing.
    if confidence_pct < AUTO_REJECT_BELOW:
        human_reviewed = False
        new_status = "resolved"
    elif confidence_pct <= AUTO_APPROVE_ABOVE:
        human_reviewed = True
        new_status = "pending_review"
    else:
        human_reviewed = False
        new_status = "resolved"

    # 7. Save the Decision, update Dispute status.
    decision = Decision(
        dispute_id=dispute_id,
        outcome=outcome,
        confidence_score=confidence_pct,
        shap_explanation=shap_explanation,
        counterfactual_text=counterfactual_text,
        evidence_completeness_pct=completeness_pct,
        human_reviewed=human_reviewed,
        reasoning_text=reasoning_text,
    )
    db.add(decision)

    dispute.status = new_status
    db.add(dispute)

    db.commit()
    db.refresh(decision)
    return decision


@router.get("/{dispute_id}/decision", response_model=DecisionOut)
def get_decision(dispute_id: int, db: Session = Depends(get_db)):
    dispute = db.get(Dispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found")

    decision = (
        db.query(Decision)
        .filter(Decision.dispute_id == dispute_id)
        .order_by(Decision.created_at.desc())
        .first()
    )
    if decision is None:
        raise HTTPException(status_code=404, detail="No decision found for this dispute yet")

    return decision
