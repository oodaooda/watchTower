from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import require_admin_token, require_api_key
from app.core.db import get_db
from app.services.signals.jobs import run_m1_hy_oas
from app.services.signals.queries import assistant_context, latest_signals, replay_events, serialize_signal, signal_history
from app.services.signals.sse import broadcaster, encode_sse

router = APIRouter(prefix="/signals", tags=["signals"])


def _require_read(authorization: str | None, db: Session) -> None:
    require_api_key(authorization, db)


def _parse_days(range_name: str | None) -> int:
    if not range_name:
        return 30
    normalized = range_name.strip().lower()
    if normalized.endswith("d"):
        try:
            return max(1, min(int(normalized[:-1]), 3650))
        except ValueError:
            return 30
    return {"1m": 30, "3m": 90, "1y": 365}.get(normalized, 30)


@router.get("/catalog")
def get_catalog(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_read(authorization, db)
    return {
        "modules": [
            {"moduleId": "M1", "title": "HY OAS", "source": "FRED", "cadence": "daily", "metric": "hy_oas_bps"},
        ]
    }


@router.get("/latest")
def get_latest(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_read(authorization, db)
    return {"signals": [serialize_signal(row) for row in latest_signals(db)]}


@router.get("/history")
def get_history(
    module_id: str,
    range: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_read(authorization, db)
    return {"signals": [serialize_signal(row) for row in signal_history(db, module_id, days=_parse_days(range))]}


@router.post("/ingest/{module_id}/run")
def run_ingest_module(
    module_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin_token(authorization)
    if module_id.upper() != "M1":
        return {"moduleId": module_id.upper(), "status": "fail", "recordsWritten": 0, "error": "module not implemented"}
    result = run_m1_hy_oas(db)
    return {
        "moduleId": result.module_id,
        "status": result.status,
        "recordsWritten": result.records_written,
        "error": result.error,
    }


@router.get("/assistant/context")
def get_assistant_context(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_read(authorization, db)
    return assistant_context(db)


@router.get("/assistant/brief")
def get_assistant_brief(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _require_read(authorization, db)
    context = assistant_context(db)
    stressed = context["stressed"]
    return {
        "regime": context["regime"]["label"],
        "summary": f"{len(stressed)} signal(s) are amber or red.",
        "stressed": stressed,
        "citations": context["citations"],
    }


@router.get("/stream")
async def stream_signals(
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_read(authorization, db)
    try:
        cursor = int(last_event_id or "0")
    except ValueError:
        cursor = 0
    replay_payloads = [
        {"id": int(event.id), "payload": event.payload}
        for event in replay_events(db, cursor)
    ]

    async def event_generator():
        for event in replay_payloads:
            yield encode_sse("signal_update", event["payload"], event_id=event["id"])

        queue = broadcaster.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                payload = broadcaster.poll(queue)
                if payload is not None:
                    yield encode_sse(payload["event"], payload["data"], event_id=payload.get("id"))
                else:
                    yield encode_sse("heartbeat", {"ok": True})
                    await asyncio.sleep(15)
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
