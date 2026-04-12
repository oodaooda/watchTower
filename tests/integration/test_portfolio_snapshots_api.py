from datetime import date

from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.models import AssetPriceDaily, Company, PortfolioPosition
from app.routers import portfolio as portfolio_router


def _build_test_client():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(portfolio_router.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def test_portfolio_snapshot_api_returns_history_and_summary():
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        asset = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity")
        db.add(asset)
        db.commit()
        db.refresh(asset)
        db.add_all(
            [
                PortfolioPosition(company_id=asset.id, quantity=10, avg_cost_basis=100),
                AssetPriceDaily(company_id=asset.id, price_date=date(2026, 4, 8), close_price=120),
                AssetPriceDaily(company_id=asset.id, price_date=date(2026, 4, 9), close_price=125),
            ]
        )
        db.commit()

    first = client.post("/portfolio/snapshots/run")
    assert first.status_code == 200
    body = first.json()
    assert len(body["snapshots"]) == 2
    assert body["snapshots"][0]["snapshot_date"] == "2026-04-08"
    assert body["snapshots"][0]["total_market_value"] == 1000.0
    assert body["snapshots"][0]["source"] == "initial_cost_basis_baseline"
    assert body["snapshots"][0]["is_inferred"] is True
    assert body["snapshots"][1]["snapshot_date"] == "2026-04-09"
    assert body["snapshots"][1]["total_market_value"] == 1250.0
    assert body["snapshots"][1]["is_inferred"] is False

    second = client.get("/portfolio/snapshots")
    assert second.status_code == 200
    assert len(second.json()["snapshots"]) == 2
    assert second.json()["summary"]["1d"] is None


def test_portfolio_snapshot_api_returns_baseline_without_real_snapshots():
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        asset = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add(asset)
        db.commit()
        db.refresh(asset)
        db.add(PortfolioPosition(company_id=asset.id, quantity=5, avg_cost_basis=400))
        db.commit()

    response = client.get("/portfolio/snapshots")
    assert response.status_code == 200
    body = response.json()
    assert len(body["snapshots"]) == 1
    assert body["snapshots"][0]["source"] == "initial_cost_basis_baseline"
    assert body["snapshots"][0]["is_inferred"] is True
    assert body["snapshots"][0]["total_market_value"] == 2000.0


def test_portfolio_price_backfill_populates_history_and_rebuilds_snapshots(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        aapl = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity", is_tracked=True)
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf", is_tracked=True)
        db.add_all([aapl, vgt])
        db.commit()
        db.refresh(aapl)
        db.refresh(vgt)
        db.add_all(
            [
                PortfolioPosition(company_id=aapl.id, quantity=10, avg_cost_basis=100),
                PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=200),
            ]
        )
        db.commit()

    monkeypatch.setattr("app.services.price_history.settings.alpha_vantage_api_key", "test-key")

    def fake_fetch(symbol, api_key):
        if symbol == "AAPL":
            return [(date(2026, 4, 8), 120.0), (date(2026, 4, 9), 125.0)]
        if symbol == "VGT":
            return [(date(2026, 4, 8), 210.0), (date(2026, 4, 9), 220.0)]
        raise AssertionError(symbol)

    monkeypatch.setattr("app.services.price_history.fetch_alpha_daily_adjusted", fake_fetch)

    response = client.post("/portfolio/prices/backfill", json={"sleep_seconds": 0, "force_refresh": True})
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded_assets"] == 2
    assert body["failed_assets"] == 0
    assert body["complete_snapshot_dates"] == 2
    assert body["latest_complete_snapshot_date"] == "2026-04-09"

    snapshots = client.get("/portfolio/snapshots")
    assert snapshots.status_code == 200
    snapshot_body = snapshots.json()
    assert [row["snapshot_date"] for row in snapshot_body["snapshots"]] == ["2026-04-07", "2026-04-08", "2026-04-09"]
    assert snapshot_body["snapshots"][1]["source"] == "asset_price_daily_backfill"
    assert snapshot_body["snapshots"][2]["total_market_value"] == 2350.0
    assert snapshot_body["summary"]["1d"]["change"] == 100.0


def test_portfolio_price_backfill_continues_when_one_symbol_fails(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        aapl = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity", is_tracked=True)
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf", is_tracked=True)
        db.add_all([aapl, vgt])
        db.commit()
        db.refresh(aapl)
        db.refresh(vgt)
        db.add_all(
            [
                PortfolioPosition(company_id=aapl.id, quantity=10, avg_cost_basis=100),
                PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=200),
            ]
        )
        db.commit()

    monkeypatch.setattr("app.services.price_history.settings.alpha_vantage_api_key", "test-key")

    def fake_fetch(symbol, api_key):
        if symbol == "AAPL":
            return [(date(2026, 4, 9), 125.0)]
        raise HTTPException(status_code=429, detail="rate limited")

    monkeypatch.setattr("app.services.price_history.fetch_alpha_daily_adjusted", fake_fetch)

    response = client.post("/portfolio/prices/backfill", json={"sleep_seconds": 0, "force_refresh": True})
    assert response.status_code == 200
    body = response.json()
    assert body["succeeded_assets"] == 1
    assert body["failed_assets"] == 1
    assert body["complete_snapshot_dates"] == 0
    assert any(item["ticker"] == "VGT" and item["status"] == "error" for item in body["items"])
