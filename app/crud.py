import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas


def create_claim(db: Session, claim_in: schemas.SurplusClaimCreate) -> models.SurplusClaim | None:
    claim = models.SurplusClaim(
        state=claim_in.state.upper(),
        county=claim_in.county,
        case_number=claim_in.case_number,
        property_address=claim_in.property_address,
        surplus_amount=claim_in.surplus_amount,
        status=str(claim_in.status.value) if claim_in.status is not None else "new",
        notes=claim_in.notes,
    )

    db.add(claim)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    db.refresh(claim)
    return claim


def get_claim_by_id(db: Session, claim_id: str, include_deleted: bool = False):
    q = db.query(models.SurplusClaim).filter(models.SurplusClaim.id == claim_id)
    if not include_deleted:
        q = q.filter(models.SurplusClaim.deleted_at.is_(None))
    return q.first()


def list_claims(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    state: Optional[str] = None,
    status: Optional[str] = None,
    county: Optional[str] = None,
    include_deleted: bool = False,
):
    q = db.query(models.SurplusClaim)

    if not include_deleted:
        q = q.filter(models.SurplusClaim.deleted_at.is_(None))

    if state:
        q = q.filter(models.SurplusClaim.state == state.upper())

    if status:
        q = q.filter(models.SurplusClaim.status == status)

    if county:
        q = q.filter(models.SurplusClaim.county.ilike(f"%{county}%"))

    return (
        q.order_by(models.SurplusClaim.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def update_claim(db: Session, claim_id: str, claim_in: schemas.SurplusClaimUpdate):
    """
    NOTE: intentionally does NOT commit.
    The route handler should commit once after writing audit rows.
    """
    claim = (
        db.query(models.SurplusClaim)
        .filter(models.SurplusClaim.id == claim_id)
        .filter(models.SurplusClaim.deleted_at.is_(None))
        .first()
    )
    if not claim:
        return None

    if claim_in.status is not None:
        claim.status = claim_in.status.value

    if claim_in.notes is not None:
        claim.notes = claim_in.notes

    claim.updated_at = datetime.utcnow()

    db.flush()  # stage changes; commit is done by route for atomic audit+update
    return claim


def soft_delete_claim(db: Session, claim_id: str) -> models.SurplusClaim | None:
    """
    NOTE: intentionally does NOT commit.
    The route handler should commit once after writing the audit row.
    """
    claim = (
        db.query(models.SurplusClaim)
        .filter(models.SurplusClaim.id == claim_id)
        .filter(models.SurplusClaim.deleted_at.is_(None))
        .first()
    )
    if not claim:
        return None

    claim.deleted_at = datetime.utcnow()
    claim.updated_at = datetime.utcnow()

    db.flush()  # stage changes; commit is done by route for atomic audit+delete
    return claim


def create_audit_log(
    db: Session,
    claim_id: str,
    action: str,
    field: str,
    old_value: Optional[str],
    new_value: Optional[str],
):
    """
    NOTE: intentionally does NOT commit.
    Caller should commit in the same transaction as the claim change.
    """
    log = models.AuditLog(
        id=str(uuid.uuid4()),
        claim_id=claim_id,
        action=action,
        field=field,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(log)
    return log


def list_audit_logs_for_claim(db: Session, claim_id: str, limit: int = 100, offset: int = 0):
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.claim_id == claim_id)
        .order_by(models.AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
