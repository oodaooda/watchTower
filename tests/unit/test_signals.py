from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import require_api_key
from app.core.db import Base
from app.core.models import ApiKey, Signal, SignalModuleState
from app.core.config import settings
from app.services.signals.queries import module_health_status
from app.services.signals.jobs import run_signal_module, write_observation
from app.services.signals.modules.e1_news_sentiment import transform_news_sentiment
from app.services.signals.modules.g1_polymarket_taiwan import (
    PolymarketMarketNotConfigured,
    polymarket_url,
    transform_polymarket_taiwan,
)
from app.services.signals.modules.m1_hy_oas import transform_fred_hy_oas
from app.services.signals.modules.m2_real_yield import transform_fred_real_yield
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


def test_m2_real_yield_transform_keeps_percent_units():
    rows = transform_fred_real_yield({"observations": [{"date": "2026-05-15", "value": "2.14"}]})

    assert len(rows) == 1
    assert rows[0].module_id == "M2"
    assert rows[0].metric == "real_yield_10y_pct"
    assert rows[0].value == 2.14
    assert rows[0].status == "amber"


def test_e1_news_sentiment_averages_top_absolute_scores():
    rows = transform_news_sentiment(
        {
            "feed": [
                {"title": "a", "url": "https://a", "time_published": "20260515T130000", "overall_sentiment_score": "0.10"},
                {"title": "b", "url": "https://b", "time_published": "20260515T140000", "overall_sentiment_score": "-0.40"},
                {"title": "c", "url": "https://c", "time_published": "20260515T150000", "overall_sentiment_score": "0.30"},
            ]
        }
    )

    assert len(rows) == 1
    assert rows[0].module_id == "E1"
    assert rows[0].entity == "top5"
    assert rows[0].value == pytest.approx(0.0)
    assert rows[0].status == "green"


def test_g1_requires_pinned_polymarket_market_id(monkeypatch):
    monkeypatch.setattr(settings, "polymarket_taiwan_market_id", None)

    with pytest.raises(PolymarketMarketNotConfigured):
        polymarket_url()


def test_g1_polymarket_transform_selects_pinned_market_yes_probability():
    rows = transform_polymarket_taiwan(
        [
            {
                "id": "1",
                "question": "Will Taiwan event happen before 2027?",
                "outcomes": '["Yes","No"]',
                "outcomePrices": '["0.12","0.88"]',
                "updatedAt": "2026-05-15T12:00:00Z",
            },
            {
                "id": "2",
                "question": "Will Taiwan risk rise?",
                "outcomes": ["Yes", "No"],
                "outcomePrices": ["0.18", "0.82"],
                "updatedAt": "2026-05-15T13:00:00Z",
            },
        ]
    )

    assert len(rows) == 1
    assert rows[0].module_id == "G1"
    assert rows[0].value == pytest.approx(18.0)
    assert rows[0].status == "red"


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


def test_module_health_status_marks_stale_or_failed_modules():
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    assert module_health_status(SignalModuleState(module_id="A", last_status="fail"), now=now) == "red"
    assert module_health_status(SignalModuleState(module_id="B"), now=now) == "grey"
    assert (
        module_health_status(
            SignalModuleState(module_id="C", last_status="ok", last_success_at=now - timedelta(days=2)),
            now=now,
        )
        == "grey"
    )
    assert module_health_status(SignalModuleState(module_id="D", last_status="ok", last_success_at=now), now=now) == "green"


def test_module_health_status_marks_unconfigured_g1_grey(monkeypatch):
    monkeypatch.setattr(settings, "polymarket_taiwan_market_id", None)

    assert (
        module_health_status(
            SignalModuleState(module_id="G1", last_status="ok", last_success_at=datetime(2026, 5, 15, tzinfo=timezone.utc)),
            now=datetime(2026, 5, 15, tzinfo=timezone.utc),
        )
        == "grey"
    )
