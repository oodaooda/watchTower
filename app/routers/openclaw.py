from __future__ import annotations

import time
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

import hashlib
from app.core.config import settings
from app.core.db import get_db, get_qa_db
from app.core.schemas import QARequest, QAResponse
from app.routers.qa import _answer_question
from app.core.models import ApiKey
from sqlalchemy import select

router = APIRouter(prefix="/openclaw", tags=["openclaw"])

_rate_state = {}


def _check_token(authorization: str | None, db: Session):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.replace("Bearer ", "", 1).strip()
    # Allow static env token as master key if configured
    if settings.openclaw_api_token and token == settings.openclaw_api_token:
        return
    if not token:
        raise HTTPException(status_code=403, detail="Invalid token")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = db.execute(
        select(ApiKey).where(ApiKey.key_hash == token_hash, ApiKey.revoked_at.is_(None))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=403, detail="Invalid token")
    row.last_used_at = datetime.utcnow()
    db.commit()


def _check_ip(request: Request):
    allowed = settings.openclaw_allowed_ips or ""
    if not allowed.strip():
        return
    allowed_set = {ip.strip() for ip in allowed.split(",") if ip.strip()}
    client_ip = request.client.host if request.client else ""
    if client_ip not in allowed_set:
        raise HTTPException(status_code=403, detail="IP not allowed")


def _rate_limit(request: Request):
    limit = settings.openclaw_rate_limit or 60
    window = 60
    client_ip = request.client.host if request.client else "unknown"
    now = int(time.time())
    bucket = _rate_state.get(client_ip, {"start": now, "count": 0})
    if now - bucket["start"] >= window:
        bucket = {"start": now, "count": 0}
    bucket["count"] += 1
    _rate_state[client_ip] = bucket
    if bucket["count"] > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@router.post("/qa", response_model=QAResponse)
def openclaw_qa(
    payload: QARequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    qa_db: Session = Depends(get_qa_db),
):
    _check_token(authorization, db)
    _check_ip(request)
    _rate_limit(request)
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    return _answer_question(question, qa_db)
