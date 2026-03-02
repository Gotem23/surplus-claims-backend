from __future__ import annotations

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import ApiKey


def _verify_key(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except Exception:
        return False


def api_key_header(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    # Client did not provide a key
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing API key"},
        )
    return x_api_key


def require_api_key(allowed_roles: set[str]):
    """
    Dependency factory:
      Depends(require_api_key({"admin"}))
      Depends(require_api_key({"admin","user"}))
      Depends(require_api_key({"admin","user","read-only"}))
    """

    def _dep(
        x_api_key: str = Depends(api_key_header),
        db: Session = Depends(get_db),
    ) -> ApiKey:
        keys = db.execute(
            select(ApiKey).where(ApiKey.is_active == True)  # noqa: E712
        ).scalars().all()

        # Server misconfiguration: no keys in DB
        if not keys:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "server_misconfig", "message": "No API keys configured"},
            )

        for k in keys:
            if _verify_key(x_api_key, k.key_hash):
                if k.role not in allowed_roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={"code": "http_error", "message": "Insufficient role"},
                    )
                return k

        # Key was provided but didn't match
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid API key"},
        )

    return _dep
