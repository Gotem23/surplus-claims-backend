from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


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
    notes: Optional[str] = None


class SurplusClaimRead(BaseModel):
    id: str
    state: str
    county: str
    case_number: str
    property_address: str
    surplus_amount: float
    status: ClaimStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # NEW: soft delete marker
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SurplusClaimUpdate(BaseModel):
    status: Optional[ClaimStatus] = None
    notes: Optional[str] = None


# Audit log read schema (since your API returns audit log lists)
class AuditLogRead(BaseModel):
    id: str
    claim_id: str
    action: str
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
