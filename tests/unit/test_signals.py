from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import require_api_key
from app.core.db import Base
from app.core.models import ApiKey, Signal
from app.services.signals.jobs import run_signal_module, write_observation
from app.services.signals.modules.m1_hy_oas import transform_fred_hy_oas
from app.services.signals.types import SignalObservation
from app.services.signals.zscore import z_score


def _session_local():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)
    return SessionLocal


def test_m1_fred_transform_skips_missing_values_and_converts_percent_to_bps():
    payload = {
        "observations": [
            {"date": "2026-05-14", "value": "."},
            {"date": "2026-05-15", "value": "3.12"},
        ]
    }

    rows = transform_fred_hy_oas(payload)

    assert len(rows) == 1
    assert rows[0].module_id == "M1"
    assert rows[0].metric == "hy_oas_bps"
    assert rows[0].value == 312.0
    assert rows[0].status == "green"
    assert rows[0].ts == datetime(2026, 5, 15, tzinfo=timezone.utc)


def test_z_score_uses_population_standard_deviation():
    assert z_score(13, [10, 10, 10]) is None
    assert z_score(14, [10, 12, 14]) == pytest.approx(1.2247448714)


def test_shared_auth_accepts_active_wt_key_and_rejects_invalid_key():
    SessionLocal = _session_local()
    raw = "wt_test_secret"
    with SessionLocal() as db:
        db.add(ApiKey(name="signals", key_prefix=raw[:8], key_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest()))
        db.commit()

        assert require_api_key(f"Bearer {raw}", db) is not None
        with pytest.raises(HTTPException):
            require_api_key("Bearer wrong", db)


def test_signal_run_writes_idempotent_rows_and_ingest_run():
    SessionLocal = _session_local()
    observation = SignalObservation(
        ts=datetime(2026, 5, 15, tzinfo=timezone.utc),
        module_id="M1",
        entity="",
        metric="hy_oas_bps",
        value=312.0,
        status="green",
        source="FRED",
        raw_payload={"date": "2026-05-15", "value": "3.12"},
    )
    with SessionLocal() as db:
        first = run_signal_module(db, module_id="M1", fetch=lambda: [observation])
        second = run_signal_module(db, module_id="M1", fetch=lambda: [observation])

        assert first.status == "ok"
        assert first.records_written == 1
        assert second.status == "ok"
        assert second.records_written == 0
        assert db.query(Signal).count() == 1


def test_signal_observation_z_score_uses_prior_rows():
    SessionLocal = _session_local()
    with SessionLocal() as db:
        for day, value in ((1, 10.0), (2, 12.0), (3, 14.0)):
            write_observation(
                db,
                SignalObservation(
                    ts=datetime(2026, 5, day, tzinfo=timezone.utc),
                    module_id="T1",
                    entity="",
                    metric="test",
                    value=value,
                    status="green",
                    source="fixture",
                    raw_payload={},
                ),
            )
            db.commit()
        row = write_observation(
            db,
            SignalObservation(
                ts=datetime(2026, 5, 4, tzinfo=timezone.utc),
                module_id="T1",
                entity="",
                metric="test",
                value=16.0,
                status="amber",
                source="fixture",
                raw_payload={},
            ),
        )
        assert row is not None
        assert row.z_score == pytest.approx(2.4494897428)
