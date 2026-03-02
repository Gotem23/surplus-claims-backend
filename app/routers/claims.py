from app.security.api_key import require_api_key
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from app import crud, schemas
from app.core.config import settings
from app.deps import get_db
from app.services.claims_service import ClaimsService

api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)

router = APIRouter(
    prefix="/claims",
    tags=["claims"],
    dependencies=[Depends(api_key_header)],
)


def get_claims_service() -> ClaimsService:
    return ClaimsService(crud)


@router.post(
    "",
    response_model=schemas.SurplusClaimRead,
    dependencies=[Depends(require_api_key({"admin", "user"}))],
)
def create_claim(
    claim: schemas.SurplusClaimCreate,
    db: Session = Depends(get_db),
):
    created = crud.create_claim(db, claim)
    if created is None:
        raise HTTPException(
            status_code=409,
            detail="Duplicate claim: a claim already exists for this state + county + case_number.",
        )
    return created


@router.get(
    "",
    dependencies=[Depends(require_api_key({"admin"}))],
)
def get_claims(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    state: str | None = Query(None, min_length=2, max_length=2),
    status: str | None = Query(None, max_length=50),
    county: str | None = Query(None, max_length=80),
    include_deleted: bool = Query(False),
    envelope: bool = Query(False),
    db: Session = Depends(get_db),
    claims_service: ClaimsService = Depends(get_claims_service),
):
    items, total = claims_service.list_claims(
        db=db,
        limit=limit,
        offset=offset,
        filters={
            "state": state,
            "status": status,
            "county": county,
            "include_deleted": include_deleted,
        },
    )

    if not envelope:
        return items

    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/{claim_id}",
    response_model=schemas.SurplusClaimRead,
    dependencies=[Depends(require_api_key({"admin", "user", "read-only"}))],
)
def get_claim(
    claim_id: str,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
):
    claim = crud.get_claim_by_id(db, claim_id, include_deleted=include_deleted)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get(
    "/{claim_id}/audit",
    response_model=list[schemas.AuditLogRead],
    dependencies=[Depends(require_api_key({"admin", "user", "read-only"}))],
)
def get_claim_audit_logs(
    claim_id: str,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    claim = crud.get_claim_by_id(db, claim_id, include_deleted=True)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return crud.list_audit_logs_for_claim(db, claim_id=claim_id, limit=limit, offset=offset)


@router.patch(
    "/{claim_id}",
    response_model=schemas.SurplusClaimRead,
    dependencies=[Depends(require_api_key({"admin", "user"}))],
)
def update_claim(
    claim_id: str,
    claim: schemas.SurplusClaimUpdate,
    db: Session = Depends(get_db),
):
    existing = crud.get_claim_by_id(db, claim_id, include_deleted=False)
    if not existing:
        raise HTTPException(status_code=404, detail="Claim not found")

    old_status = existing.status
    old_notes = existing.notes

    try:
        updated = crud.update_claim(db, claim_id, claim)
        if not updated:
            raise HTTPException(status_code=404, detail="Claim not found")

        if claim.status is not None and str(old_status) != str(updated.status):
            crud.create_audit_log(
                db=db,
                claim_id=claim_id,
                action="update",
                field="status",
                old_value=str(old_status),
                new_value=str(updated.status),
            )

        if claim.notes is not None and (old_notes or "") != (updated.notes or ""):
            crud.create_audit_log(
                db=db,
                claim_id=claim_id,
                action="update",
                field="notes",
                old_value=old_notes,
                new_value=updated.notes,
            )

        db.commit()
        db.refresh(updated)
        return updated

    except Exception:
        db.rollback()
        raise


@router.delete(
    "/{claim_id}",
    response_model=schemas.SurplusClaimRead,
    dependencies=[Depends(require_api_key({"admin"}))],
)
def delete_claim(
    claim_id: str,
    db: Session = Depends(get_db),
):
    existing = crud.get_claim_by_id(db, claim_id, include_deleted=False)
    if not existing:
        raise HTTPException(status_code=404, detail="Claim not found")

    try:
        deleted = crud.soft_delete_claim(db, claim_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Claim not found")

        crud.create_audit_log(
            db=db,
            claim_id=claim_id,
            action="delete",
            field="deleted_at",
            old_value=None,
            new_value=str(deleted.deleted_at),
        )

        db.commit()
        db.refresh(deleted)
        return deleted

    except Exception:
        db.rollback()
        raise


@router.post(
    "/{claim_id}/restore",
    response_model=schemas.SurplusClaimRead,
    dependencies=[Depends(require_api_key({"admin"}))],
)
def restore_claim(
    claim_id: str,
    db: Session = Depends(get_db),
):
    claim = crud.get_claim_by_id(db, claim_id, include_deleted=True)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.deleted_at is None:
        return claim

    claim.deleted_at = None
    crud.create_audit_log(
        db=db,
        claim_id=claim_id,
        action="restore",
        field="deleted_at",
        old_value="restored_from_deleted",
        new_value=None,
    )
    db.commit()
    db.refresh(claim)
    return claim
