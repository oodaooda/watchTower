from __future__ import annotations

import hashlib
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import ApiKey


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        raise HTTPException(status_code=403, detail="Invalid token")
    return token


def require_api_key(authorization: str | None, db: Session) -> ApiKey | None:
    token = bearer_token(authorization)
    if settings.openclaw_api_token and token == settings.openclaw_api_token:
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = db.execute(
        select(ApiKey).where(ApiKey.key_hash == token_hash, ApiKey.revoked_at.is_(None))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=403, detail="Invalid token")
    row.last_used_at = datetime.utcnow()
    db.commit()
    return row


def require_admin_token(authorization: str | None) -> None:
    token = settings.admin_settings_token
    if not token:
        raise HTTPException(status_code=503, detail="Settings admin token not configured")
    if bearer_token(authorization) != token:
        raise HTTPException(status_code=403, detail="Invalid token")
