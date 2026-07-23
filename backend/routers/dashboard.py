"""
dashboard.py

Aggregated metrics across all resolved disputes: outcome rates, average
resolution time, confidence score distribution, and percent human-reviewed.
"""

from datetime import timezone
from statistics import mean

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Decision, Dispute

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    decisions = db.query(Decision).all()
    total = len(decisions)

    if total == 0:
        return {
            "total_decisions": 0,
            "outcome_rates": {"refund": 0.0, "deny": 0.0, "partial": 0.0},
            "avg_resolution_time_seconds": None,
            "confidence_distribution": {},
            "pct_human_reviewed": 0.0,
        }

    # Outcome rates.
    outcome_counts = {"refund": 0, "deny": 0, "partial": 0}
    for d in decisions:
        if d.outcome in outcome_counts:
            outcome_counts[d.outcome] += 1
    outcome_rates = {k: round(100 * v / total, 2) for k, v in outcome_counts.items()}

    # Average resolution time: dispute creation -> decision creation.
    resolution_times = []
    for d in decisions:
        dispute = db.get(Dispute, d.dispute_id)
        if dispute is None or dispute.created_at is None or d.created_at is None:
            continue
        created = dispute.created_at
        decided = d.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if decided.tzinfo is None:
            decided = decided.replace(tzinfo=timezone.utc)
        resolution_times.append((decided - created).total_seconds())

    avg_resolution_time_seconds = round(mean(resolution_times), 2) if resolution_times else None

    # Confidence score distribution, bucketed.
    buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-85": 0, "85-100": 0}
    for d in decisions:
        c = d.confidence_score
        if c < 20:
            buckets["0-20"] += 1
        elif c < 40:
            buckets["20-40"] += 1
        elif c < 60:
            buckets["40-60"] += 1
        elif c <= 85:
            buckets["60-85"] += 1
        else:
            buckets["85-100"] += 1

    pct_human_reviewed = round(
        100 * sum(1 for d in decisions if d.human_reviewed) / total, 2
    )

    return {
        "total_decisions": total,
        "outcome_rates": outcome_rates,
        "avg_resolution_time_seconds": avg_resolution_time_seconds,
        "confidence_distribution": buckets,
        "pct_human_reviewed": pct_human_reviewed,
    }
