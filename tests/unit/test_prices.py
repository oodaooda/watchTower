from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.core.models import Company
from app.routers.prices import _build_change_summary, _slice_daily
from app.services import price_history


def test_slice_daily_supports_three_month_range():
    points = [
        (datetime(2025, 12, 1), 100.0),
        (datetime(2026, 1, 15), 110.0),
        (datetime(2026, 2, 15), 120.0),
        (datetime(2026, 3, 15), 130.0),
    ]

    sliced = _slice_daily(points, "3m")
    assert len(sliced) == 3
    assert sliced[0][0] == datetime(2026, 1, 15)


def test_build_change_summary_reports_day_month_year_changes():
    points = [
        (datetime(2025, 3, 1), 100.0),
        (datetime(2026, 2, 1), 120.0),
        (datetime(2026, 3, 1), 140.0),
        (datetime(2026, 3, 2), 150.0),
    ]

    summary = _build_change_summary(points)
    assert summary["1d"]["change"] == 10.0
    assert summary["1m"]["change"] == 30.0
    assert summary["1y"]["change"] == 50.0


def test_sync_tracked_assets_daily_history_retries_after_rate_limit(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add_all(
            [
                Company(ticker="AAPL", name="Apple Inc.", is_tracked=True),
                Company(ticker="MSFT", name="Microsoft Corp.", is_tracked=True),
            ]
        )
        db.commit()

        monkeypatch.setattr(price_history.settings, "alpha_vantage_api_key", "test-key")
        sleeps: list[float] = []
        monkeypatch.setattr(price_history.time, "sleep", lambda seconds: sleeps.append(seconds))

        attempts = {"AAPL": 0, "MSFT": 0}

        def fake_ensure_daily_history(db_session, asset, force_refresh=False):
            attempts[asset.ticker] += 1
            if asset.ticker == "MSFT" and attempts[asset.ticker] == 1:
                raise HTTPException(status_code=429, detail="rate limited")
            return []

        monkeypatch.setattr(price_history, "ensure_daily_history", fake_ensure_daily_history)

        synced = price_history.sync_tracked_assets_daily_history(db)
        assert synced == 2
        assert attempts["AAPL"] == 1
        assert attempts["MSFT"] == 2
        assert sleeps.count(price_history.DEFAULT_ALPHA_DAILY_SLEEP_SECONDS) == 1
        assert price_history.ALPHA_RATE_LIMIT_RETRY_SECONDS in sleeps
