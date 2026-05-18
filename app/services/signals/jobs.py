from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Signal, SignalEvent, SignalIngestRun, SignalModuleState
from app.services.signals.modules.e1_news_sentiment import MODULE_ID as E1_MODULE_ID, fetch_observations as fetch_e1
from app.services.signals.modules.g1_polymarket_taiwan import MODULE_ID as G1_MODULE_ID, fetch_observations as fetch_g1
from app.services.signals.modules.m1_hy_oas import MODULE_ID as M1_MODULE_ID, fetch_observations as fetch_m1
from app.services.signals.modules.m2_real_yield import MODULE_ID as M2_MODULE_ID, fetch_observations as fetch_m2
from app.services.signals.sse import broadcaster
from app.services.signals.types import SignalObservation, SignalRunResult
from app.services.signals.zscore import z_score

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _history_values(db: Session, observation: SignalObservation) -> list[float]:
    start = observation.ts - timedelta(days=365)
    rows = db.execute(
        select(Signal.value)
        .where(
            Signal.module_id == observation.module_id,
            Signal.metric == observation.metric,
            Signal.entity == observation.entity,
            Signal.ts >= start,
            Signal.ts < observation.ts,
        )
        .order_by(Signal.ts)
    ).scalars().all()
    return [float(value) for value in rows]


def _event_payload(row: Signal, event_id: int) -> dict:
    return {
        "id": event_id,
        "moduleId": row.module_id,
        "ts": row.ts.isoformat(),
        "entity": row.entity,
        "metric": row.metric,
        "value": float(row.value),
        "zScore": float(row.z_score) if row.z_score is not None else None,
        "status": row.status,
        "source": row.source,
    }


def write_observation(db: Session, observation: SignalObservation) -> Signal | None:
    existing = db.execute(
        select(Signal).where(
            Signal.module_id == observation.module_id,
            Signal.ts == observation.ts,
            Signal.metric == observation.metric,
            Signal.entity == observation.entity,
        )
    ).scalar_one_or_none()
    if existing:
        return None

    row = Signal(
        ts=observation.ts,
        module_id=observation.module_id,
        entity=observation.entity,
        metric=observation.metric,
        value=observation.value,
        z_score=z_score(observation.value, _history_values(db, observation)),
        status=observation.status,
        source=observation.source,
        raw_payload=observation.raw_payload,
    )
    db.add(row)
    db.flush()
    event = SignalEvent(
        module_id=row.module_id,
        signal_id=row.id,
        payload=_event_payload(row, 0),
    )
    db.add(event)
    db.flush()
    event.payload = _event_payload(row, int(event.id))
    return row


def _update_module_state(db: Session, module_id: str, status: str, error: str | None = None) -> None:
    now = _utcnow()
    state = db.get(SignalModuleState, module_id)
    if not state:
        state = SignalModuleState(module_id=module_id)
        db.add(state)
    state.last_attempt_at = now
    state.last_status = status
    state.last_error = error
    state.updated_at = now
    if status == "ok":
        state.last_success_at = now


def run_signal_module(
    db: Session,
    *,
    module_id: str,
    fetch: Callable[[], list[SignalObservation]],
) -> SignalRunResult:
    run = SignalIngestRun(module_id=module_id, status="fail", records_written=0)
    db.add(run)
    db.commit()
    db.refresh(run)
    records_written = 0
    try:
        observations = fetch()
        for observation in observations:
            row = write_observation(db, observation)
            if row is not None:
                records_written += 1
        run.status = "ok"
        run.records_written = records_written
        run.finished_at = _utcnow()
        _update_module_state(db, module_id, "ok")
        db.commit()

        events = db.execute(
            select(SignalEvent)
            .where(SignalEvent.module_id == module_id)
            .order_by(SignalEvent.id.desc())
            .limit(records_written)
        ).scalars().all()
        for event in reversed(events):
            broadcaster.publish({"event": "signal_update", "id": int(event.id), "data": event.payload})
        return SignalRunResult(module_id=module_id, status="ok", records_written=records_written)
    except Exception as exc:
        log.exception("signal_module_failed module_id=%s", module_id)
        run.status = "fail"
        run.error = str(exc)
        run.finished_at = _utcnow()
        _update_module_state(db, module_id, "fail", str(exc))
        db.commit()
        return SignalRunResult(module_id=module_id, status="fail", records_written=records_written, error=str(exc))


def run_m1_hy_oas(db: Session) -> SignalRunResult:
    return run_signal_module(db, module_id=M1_MODULE_ID, fetch=fetch_m1)


def run_m2_real_yield(db: Session) -> SignalRunResult:
    return run_signal_module(db, module_id=M2_MODULE_ID, fetch=fetch_m2)


def run_e1_news_sentiment(db: Session) -> SignalRunResult:
    return run_signal_module(db, module_id=E1_MODULE_ID, fetch=fetch_e1)


def run_g1_polymarket_taiwan(db: Session) -> SignalRunResult:
    return run_signal_module(db, module_id=G1_MODULE_ID, fetch=fetch_g1)


RUNNERS = {
    M1_MODULE_ID: run_m1_hy_oas,
    M2_MODULE_ID: run_m2_real_yield,
    E1_MODULE_ID: run_e1_news_sentiment,
    G1_MODULE_ID: run_g1_polymarket_taiwan,
}
