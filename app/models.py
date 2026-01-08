import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Numeric, Text, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class SurplusClaim(Base):
    __tablename__ = "surplus_claims"

    __table_args__ = (
        UniqueConstraint("state", "county", "case_number", name="uq_claim_state_county_case"),
        CheckConstraint(
            "status IN ('new','researching','contacted','paperwork_ready','filed','approved','paid','closed')",
            name="ck_claim_status_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    state: Mapped[str] = mapped_column(String(2), index=True)
    county: Mapped[str] = mapped_column(String(120), index=True)
    case_number: Mapped[str] = mapped_column(String(120), index=True)
    property_address: Mapped[str] = mapped_column(String(255))
    surplus_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    status: Mapped[str] = mapped_column(String(50), default="new")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Soft delete flag (NULL = active, timestamp = deleted)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = Column(String(36), ForeignKey("surplus_claims.id", ondelete="CASCADE"), nullable=False, index=True)

    action = Column(String(50), nullable=False)  # e.g. "update", "delete"
    field = Column(String(50), nullable=False)   # e.g. "status", "notes", "deleted_at"

    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
