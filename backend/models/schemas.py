"""
schemas.py

Pydantic request/response models for the dispute endpoints. Separate from
db_models.py (the SQLAlchemy ORM models) so API contracts can evolve
independently of storage.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class DisputeCreate(BaseModel):
    card_member_id: str
    merchant_id: str
    reason_code: str
    amount: float


class DisputeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_member_id: str
    merchant_id: str
    reason_code: str
    amount: float
    status: str
    created_at: datetime


class EvidenceCreate(BaseModel):
    evidence_type: str
    raw_text: str
    submitted_by: str = "card_member"


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dispute_id: int
    submitted_by: str
    evidence_type: str
    raw_text: Optional[str] = None
    parsed_fields: Optional[Any] = None
    uploaded_at: datetime


class StatusOut(BaseModel):
    dispute_id: int
    status: str
    evidence_count: int


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dispute_id: int
    outcome: str
    confidence_score: float
    shap_explanation: Optional[Any] = None
    counterfactual_text: Optional[str] = None
    evidence_completeness_pct: Optional[float] = None
    human_reviewed: bool
    reasoning_text: Optional[str] = None
    created_at: datetime
