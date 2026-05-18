from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Signal, SignalEvent, SignalIngestRun, SignalModuleState

KNOWN_MODULE_IDS = ("M1", "M2", "E1", "G1")


def module_is_configured(module_id: str) -> bool:
    if module_id == "G1":
        return bool(settings.polymarket_taiwan_market_id)
    return True


def module_health_status(row: SignalModuleState, *, now: datetime | None = None) -> str:
    if not module_is_configured(row.module_id):
        return "grey"
    if row.last_status == "fail":
        return "red"
    if row.last_success_at is None:
        return "grey"
    current = now or datetime.now(timezone.utc)
    last_success = row.last_success_at
    if last_success.tzinfo is None:
        last_success = last_success.replace(tzinfo=timezone.utc)
    if current - last_success > timedelta(hours=24):
        return "grey"
    if row.last_status == "partial":
        return "amber"
    return "green"


def serialize_signal(row: Signal) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "ts": row.ts.isoformat(),
        "moduleId": row.module_id,
        "entity": row.entity,
        "metric": row.metric,
        "value": float(row.value),
        "zScore": float(row.z_score) if row.z_score is not None else None,
        "status": row.status,
        "source": row.source,
        "rawPayload": row.raw_payload,
    }


def latest_signals(db: Session) -> list[Signal]:
    rows = db.execute(select(Signal).order_by(Signal.module_id, Signal.ts.desc())).scalars().all()
    latest: dict[tuple[str, str, str], Signal] = {}
    for row in rows:
        if not module_is_configured(row.module_id):
            continue
        key = (row.module_id, row.metric, row.entity)
        if key not in latest:
            latest[key] = row
    return list(latest.values())


def signal_history(db: Session, module_id: str, *, days: int = 30) -> list[Signal]:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return db.execute(
        select(Signal)
        .where(Signal.module_id == module_id, Signal.ts >= start)
        .order_by(Signal.ts)
    ).scalars().all()


def replay_events(db: Session, after_id: int, *, limit: int = 1000) -> list[SignalEvent]:
    return db.execute(
        select(SignalEvent)
        .where(SignalEvent.id > after_id)
        .order_by(SignalEvent.id)
        .limit(limit)
    ).scalars().all()


def assistant_context(db: Session) -> dict[str, Any]:
    latest = latest_signals(db)
    state_rows = {row.module_id: row for row in db.execute(select(SignalModuleState)).scalars().all()}
    module_ids = sorted(set(KNOWN_MODULE_IDS) | set(state_rows))
    recent_runs = db.execute(
        select(SignalIngestRun).order_by(SignalIngestRun.started_at.desc()).limit(10)
    ).scalars().all()
    stressed = [row for row in latest if row.status in {"amber", "red"}]
    return {
        "regime": {
            "label": "STRESSED" if any(row.status == "red" for row in latest) else "MIXED" if stressed else "BENIGN",
            "contributors": [serialize_signal(row) for row in stressed],
        },
        "latest": [serialize_signal(row) for row in latest],
        "stressed": [serialize_signal(row) for row in stressed],
        "moduleStates": [_serialize_module_state(module_id, state_rows.get(module_id)) for module_id in module_ids],
        "recentRuns": [
            {
                "id": int(row.id),
                "moduleId": row.module_id,
                "startedAt": row.started_at.isoformat() if row.started_at else None,
                "finishedAt": row.finished_at.isoformat() if row.finished_at else None,
                "status": row.status,
                "error": row.error,
                "recordsWritten": row.records_written,
            }
            for row in recent_runs
        ],
        "citations": sorted({row.source for row in latest}),
    }


def _serialize_module_state(module_id: str, row: SignalModuleState | None) -> dict[str, Any]:
    configured = module_is_configured(module_id)
    if row is None:
        return {
            "moduleId": module_id,
            "enabled": True,
            "configured": configured,
            "lastSuccessAt": None,
            "lastAttemptAt": None,
            "lastStatus": None,
            "healthStatus": "grey",
            "lastError": None if configured else f"{module_id} is not configured",
        }
    return {
        "moduleId": row.module_id,
        "enabled": bool(row.enabled),
        "configured": configured,
        "lastSuccessAt": row.last_success_at.isoformat() if row.last_success_at else None,
        "lastAttemptAt": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
        "lastStatus": row.last_status,
        "healthStatus": module_health_status(row),
        "lastError": row.last_error if configured else f"{module_id} is not configured",
    }
