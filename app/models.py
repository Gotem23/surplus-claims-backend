import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import INET, UUID as PgUUID
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
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id = Column(
        String(36),
        ForeignKey("surplus_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action = Column(String(50), nullable=False)
    field = Column(String(50), nullable=False)

    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApiKey(Base):
    __tablename__ = "api_keys"

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'expiring', 'revoked', 'expired')",
            name="api_keys_status_check",
        ),
        # Partial unique: only one active key per (tenant, name)
        Index(
            "uq_api_keys_tenant_name_active",
            "tenant_id",
            "name",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index("ix_api_keys_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        PgUUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tenant / lifecycle fields (added in schema migration)
    tenant_id: Mapped[str] = mapped_column(PgUUID(as_uuid=False), nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Audit provenance
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_actor_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_by_actor_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked_by_actor_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Key rotation chain (self-referencing)
    rotated_from_key_id: Mapped[str | None] = mapped_column(
        PgUUID(as_uuid=False),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rotated_to_key_id: Mapped[str | None] = mapped_column(
        PgUUID(as_uuid=False),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rotation_grace_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_ip: Mapped[str | None] = mapped_column(INET, nullable=True)
