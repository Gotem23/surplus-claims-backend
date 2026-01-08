import os

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from app.deps import get_db
from app import schemas, crud

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Enable only when behind HTTPS (prod)
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


app = FastAPI(title="Surplus Claims API")


CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]


app = FastAPI()

# --- Security headers ---
app.add_middleware(SecurityHeadersMiddleware)


# --- CORS allowlist ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/")
def root():
    return {"message": "Surplus Claims API is running"}



@app.post(
    "/claims",
    response_model=schemas.SurplusClaimRead,
    responses={
        409: {
            "description": "Duplicate claim",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Duplicate claim: a claim already exists for this state + county + case_number."
                    }
                }
            },
        }
    },
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


@app.get("/claims", response_model=list[schemas.SurplusClaimRead])
def get_claims(
    limit: int = 50,
    offset: int = 0,
    state: Optional[str] = None,
    status: Optional[str] = None,
    county: Optional[str] = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
):
    return crud.list_claims(
        db,
        limit=limit,
        offset=offset,
        state=state,
        status=status,
        county=county,
        include_deleted=include_deleted,
    )


@app.get("/claims/{claim_id}", response_model=schemas.SurplusClaimRead)
def get_claim(claim_id: str, include_deleted: bool = False, db: Session = Depends(get_db)):
    claim = crud.get_claim_by_id(db, claim_id, include_deleted=include_deleted)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@app.get("/claims/{claim_id}/audit", response_model=list[schemas.AuditLogRead])
def get_claim_audit_logs(
    claim_id: str,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    claim = crud.get_claim_by_id(db, claim_id, include_deleted=True)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return crud.list_audit_logs_for_claim(db, claim_id=claim_id, limit=limit, offset=offset)


@app.patch("/claims/{claim_id}", response_model=schemas.SurplusClaimRead)
def update_claim(claim_id: str, claim: schemas.SurplusClaimUpdate, db: Session = Depends(get_db)):
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



@app.delete("/claims/{claim_id}", response_model=schemas.SurplusClaimRead)
def delete_claim(claim_id: str, db: Session = Depends(get_db)):
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


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}