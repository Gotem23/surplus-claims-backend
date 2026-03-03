from fastapi import APIRouter, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from app import crud, schemas
from app.core.config import settings
from app.deps import get_db
from app.security.api_key import require_api_key
from app.services.claims_service import ClaimsService

api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)

router = APIRouter(
    prefix="/assist",
    tags=["assist"],
    dependencies=[Depends(api_key_header)],
)


def get_claims_service() -> ClaimsService:
    return ClaimsService(crud)


@router.get(
    "/claims/{claim_id}/next-steps",
    response_model=schemas.NextStepsResponse,
    dependencies=[Depends(require_api_key({"admin", "user", "read-only"}))],
    summary="Get valid next workflow steps for a claim",
)
def get_next_steps(
    claim_id: str,
    db: Session = Depends(get_db),
    claims_service: ClaimsService = Depends(get_claims_service),
):
    """Returns the claim's current status and all valid transitions it can move to,
    including human-readable labels and descriptions.

    The `natural_next` field identifies the primary forward target used by the
    advance endpoint.
    """
    return claims_service.get_next_steps_response(db, claim_id)


@router.post(
    "/claims/{claim_id}/advance",
    response_model=schemas.SurplusClaimRead,
    dependencies=[Depends(require_api_key({"admin", "user"}))],
    summary="Advance a claim to its next natural workflow status",
)
def advance_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    claims_service: ClaimsService = Depends(get_claims_service),
):
    """Advances the claim to the first valid next status (the `natural_next` from
    the next-steps response) and records an audit log entry.

    Returns 409 if the claim is already in the terminal `closed` state.
    Returns 410 if the claim has been soft-deleted.
    """
    try:
        updated = claims_service.advance_claim(db, claim_id)
        db.commit()
        db.refresh(updated)
        return updated
    except Exception:
        db.rollback()
        raise
