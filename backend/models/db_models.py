"""
db_models.py

SQLAlchemy ORM models for the dispute resolution pipeline: Dispute,
Evidence, and Decision.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    card_member_id = Column(String, nullable=False, index=True)
    merchant_id = Column(String, nullable=False, index=True)
    reason_code = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    evidence = relationship(
        "Evidence", back_populates="dispute", cascade="all, delete-orphan"
    )
    decisions = relationship(
        "Decision", back_populates="dispute", cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    dispute_id = Column(Integer, ForeignKey("disputes.id"), nullable=False, index=True)
    submitted_by = Column(String, nullable=False)
    evidence_type = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)
    parsed_fields = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    dispute = relationship("Dispute", back_populates="evidence")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    dispute_id = Column(Integer, ForeignKey("disputes.id"), nullable=False, index=True)
    outcome = Column(String, nullable=False)
    confidence_score = Column(Float, nullable=False)
    shap_explanation = Column(JSON, nullable=True)
    counterfactual_text = Column(Text, nullable=True)
    evidence_completeness_pct = Column(Float, nullable=True)
    human_reviewed = Column(Boolean, nullable=False, default=False)
    reasoning_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    dispute = relationship("Dispute", back_populates="decisions")
