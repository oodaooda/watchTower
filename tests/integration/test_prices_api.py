from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.models import Company
from app.routers import prices as prices_router


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
    app.include_router(prices_router.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def test_price_history_endpoint_persists_daily_history(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        db.add(Company(ticker="VGT", name="VGT ETF", asset_type="etf", is_tracked=True))
        db.commit()

    monkeypatch.setattr(prices_router.settings, "alpha_vantage_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.price_history.fetch_alpha_daily_adjusted",
        lambda symbol, api_key: [
            (date(2026, 1, 2), 100.0),
            (date(2026, 2, 2), 110.0),
            (date(2026, 3, 2), 120.0),
        ],
    )

    response = client.get("/prices/VGT/history?range=1y")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "VGT"
    assert body["interval"] == "1d"
    assert len(body["points"]) == 3
    assert body["summary"]["1d"]["change"] == 10.0
    assert body["summary"]["1m"]["change"] == 10.0

    with SessionLocal() as db:
        from app.core.models import AssetPriceDaily

        rows = db.query(AssetPriceDaily).all()
        assert len(rows) == 3


def test_price_history_range_supports_three_months(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        db.add(Company(ticker="AAPL", name="Apple Inc.", asset_type="equity", is_tracked=True))
        db.commit()

    monkeypatch.setattr(prices_router.settings, "alpha_vantage_api_key", "test-key")
    monkeypatch.setattr(
        "app.services.price_history.fetch_alpha_daily_adjusted",
        lambda symbol, api_key: [
            (date(2025, 12, 30), 90.0),
            (date(2026, 1, 15), 95.0),
            (date(2026, 2, 15), 105.0),
            (date(2026, 3, 15), 120.0),
        ],
    )

    response = client.get("/prices/AAPL/history?range=3m")
    assert response.status_code == 200
    body = response.json()
    assert len(body["points"]) == 4
