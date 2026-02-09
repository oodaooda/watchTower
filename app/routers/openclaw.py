from __future__ import annotations

import time
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.schemas import QARequest, QAResponse
from app.routers.qa import _answer_question

router = APIRouter(prefix="/openclaw", tags=["openclaw"])

_rate_state = {}


def _check_token(authorization: str | None):
    token = settings.openclaw_api_token
    if not token:
        raise HTTPException(status_code=503, detail="OpenClaw API token not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if authorization.replace("Bearer ", "", 1).strip() != token:
        raise HTTPException(status_code=403, detail="Invalid token")


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
):
    _check_token(authorization)
    _check_ip(request)
    _rate_limit(request)
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    return _answer_question(question, db)
