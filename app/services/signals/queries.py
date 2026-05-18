from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Signal, SignalEvent, SignalIngestRun, SignalModuleState


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
    states = db.execute(select(SignalModuleState)).scalars().all()
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
        "moduleStates": [
            {
                "moduleId": row.module_id,
                "enabled": bool(row.enabled),
                "lastSuccessAt": row.last_success_at.isoformat() if row.last_success_at else None,
                "lastAttemptAt": row.last_attempt_at.isoformat() if row.last_attempt_at else None,
                "lastStatus": row.last_status,
                "lastError": row.last_error,
            }
            for row in states
        ],
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
