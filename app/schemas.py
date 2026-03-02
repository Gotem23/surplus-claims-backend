from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ClaimStatus(str, Enum):
    new = "new"
    researching = "researching"
    contacted = "contacted"
    paperwork_ready = "paperwork_ready"
    filed = "filed"
    approved = "approved"
    paid = "paid"
    closed = "closed"


class SurplusClaimCreate(BaseModel):
    state: str = Field(min_length=2, max_length=2)
    county: str = Field(min_length=1, max_length=120)
    case_number: str = Field(min_length=1, max_length=120)
    property_address: str = Field(min_length=1, max_length=255)
    surplus_amount: float = Field(default=0, ge=0)
    status: ClaimStatus = Field(default=ClaimStatus.new)
    notes: str | None = None


class SurplusClaimRead(BaseModel):
    id: str
    state: str
    county: str
    case_number: str
    property_address: str
    surplus_amount: float
    status: ClaimStatus
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    # NEW: soft delete marker
    deleted_at: datetime | None = None

    class Config:
        from_attributes = True


class SurplusClaimUpdate(BaseModel):
    status: ClaimStatus | None = None
    notes: str | None = None


# Audit log read schema (since your API returns audit log lists)
class AuditLogRead(BaseModel):
    id: str
    claim_id: str
    action: str
    field: str
    old_value: str | None = None
    new_value: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ClaimsPage(BaseModel):
    items: list[SurplusClaimRead]
    total: int
    limit: int
    offset: int
