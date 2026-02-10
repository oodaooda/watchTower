from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import ApiKey, AppSetting
from app.core.schemas import ApiKeyCreateIn, ApiKeyCreateOut, ApiKeyOut, SettingsIn, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])

SETTING_MAX_KEYS = "openclaw_max_keys"


def _require_admin(authorization: str | None):
    token = settings.admin_settings_token
    if not token:
        raise HTTPException(status_code=503, detail="Settings admin token not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if authorization.replace("Bearer ", "", 1).strip() != token:
        raise HTTPException(status_code=403, detail="Invalid token")


def _get_max_keys(db: Session) -> int:
    row = db.execute(select(AppSetting).where(AppSetting.key == SETTING_MAX_KEYS)).scalar_one_or_none()
    if not row:
        return 2
    try:
        return int(row.value)
    except ValueError:
        return 2


def _set_max_keys(db: Session, value: int) -> None:
    row = db.execute(select(AppSetting).where(AppSetting.key == SETTING_MAX_KEYS)).scalar_one_or_none()
    if row:
        row.value = str(value)
    else:
        db.add(AppSetting(key=SETTING_MAX_KEYS, value=str(value)))


@router.get("/openclaw", response_model=SettingsOut)
def get_openclaw_settings(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)
    max_keys = _get_max_keys(db)
    active = db.execute(select(func.count(ApiKey.id)).where(ApiKey.revoked_at.is_(None))).scalar() or 0
    return SettingsOut(openclaw_max_keys=max_keys, active_keys=int(active))


@router.post("/openclaw", response_model=SettingsOut)
def set_openclaw_settings(
    payload: SettingsIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)
    value = max(1, min(payload.openclaw_max_keys, 10))
    _set_max_keys(db, value)
    db.commit()
    active = db.execute(select(func.count(ApiKey.id)).where(ApiKey.revoked_at.is_(None))).scalar() or 0
    return SettingsOut(openclaw_max_keys=value, active_keys=int(active))


@router.get("/openclaw/keys", response_model=list[ApiKeyOut])
def list_keys(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)
    rows = db.execute(select(ApiKey).order_by(ApiKey.created_at.desc())).scalars().all()
    return [ApiKeyOut.model_validate(r) for r in rows]


@router.post("/openclaw/keys", response_model=ApiKeyCreateOut)
def create_key(
    payload: ApiKeyCreateIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)
    max_keys = _get_max_keys(db)
    active = db.execute(select(func.count(ApiKey.id)).where(ApiKey.revoked_at.is_(None))).scalar() or 0
    if active >= max_keys:
        raise HTTPException(status_code=400, detail="Max active keys reached")

    raw = "wt_" + secrets.token_hex(24)
    prefix = raw[:8]
    key_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    row = ApiKey(name=payload.name, key_prefix=prefix, key_hash=key_hash)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiKeyCreateOut(id=row.id, name=row.name, key=raw, key_prefix=row.key_prefix)


@router.post("/openclaw/keys/{key_id}/revoke")
def revoke_key(
    key_id: int,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)
    row = db.get(ApiKey, key_id)
    if not row:
        raise HTTPException(status_code=404, detail="Key not found")
    row.revoked_at = datetime.utcnow()
    db.commit()
    return {"status": "revoked"}
