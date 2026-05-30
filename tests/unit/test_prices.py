from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.core.models import AssetPriceDaily, Company, PortfolioPosition
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


def test_expected_latest_eod_date_waits_until_after_close_buffer():
    before_ready = datetime.fromisoformat("2026-04-28T16:30:00-04:00")
    after_ready = datetime.fromisoformat("2026-04-28T18:30:00-04:00")
    weekend = datetime.fromisoformat("2026-05-02T12:00:00-04:00")
    memorial_day = datetime.fromisoformat("2026-05-25T18:30:00-04:00")

    assert price_history.expected_latest_eod_date(before_ready).isoformat() == "2026-04-27"
    assert price_history.expected_latest_eod_date(after_ready).isoformat() == "2026-04-28"
    assert price_history.expected_latest_eod_date(weekend).isoformat() == "2026-05-01"
    assert price_history.expected_latest_eod_date(memorial_day).isoformat() == "2026-05-22"


def test_cash_assets_get_synthetic_daily_prices_without_api(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        cash = Company(ticker="CASH_TOTAL", name="Cash Total", asset_type="cash")
        db.add(cash)
        db.commit()
        db.refresh(cash)

        monkeypatch.setattr(price_history.settings, "alpha_vantage_api_key", None)
        monkeypatch.setattr(
            price_history,
            "expected_latest_eod_date",
            lambda now=None: date(2026, 5, 13),
        )

        rows = price_history.ensure_daily_history(db, cash)
        assert rows[-1].price_date == date(2026, 5, 13)
        assert float(rows[-1].close_price) == 1.0
        assert db.query(AssetPriceDaily).count() == 1


def test_complete_portfolio_price_dates_excludes_market_holidays():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        asset = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity")
        db.add(asset)
        db.commit()
        db.refresh(asset)
        db.add(PortfolioPosition(company_id=asset.id, quantity=10, avg_cost_basis=100))
        db.add_all(
            [
                AssetPriceDaily(company_id=asset.id, price_date=date(2026, 5, 22), close_price=100),
                AssetPriceDaily(company_id=asset.id, price_date=date(2026, 5, 25), close_price=100),
                AssetPriceDaily(company_id=asset.id, price_date=date(2026, 5, 26), close_price=100),
            ]
        )
        db.commit()

        assert price_history.complete_portfolio_price_dates(db) == [date(2026, 5, 22), date(2026, 5, 26)]


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
