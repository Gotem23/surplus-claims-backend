from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.deps import get_db

router = APIRouter(tags=["public"])


@router.get("/")
def root():
    return {"message": "Surplus Claims API is running"}


@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)):
    # Explicit anti-cache headers for health checks
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
