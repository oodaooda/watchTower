from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.models import Company
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


def test_create_update_delete_mixed_portfolio_positions(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        db.add_all(
            [
                Company(ticker="AAPL", name="Apple Inc.", asset_type="equity"),
                Company(ticker="VGT", name="VGT ETF", asset_type="etf"),
            ]
        )
        db.commit()

    monkeypatch.setattr(
        portfolio_router,
        "fetch_alpha_quotes",
        lambda tickers: {
            "AAPL": {"price": 200.0, "source": "alpha_vantage", "status": "live"},
            "VGT": {"price": 450.0, "source": "alpha_vantage", "status": "live"},
        },
    )

    create_aapl = client.post("/portfolio", json={"ticker": "AAPL", "quantity": 10, "avg_cost_basis": 150})
    assert create_aapl.status_code == 200
    body = create_aapl.json()
    assert len(body["positions"]) == 1
    assert body["summary"]["total_market_value"] == 2000.0

    create_vgt = client.post("/portfolio", json={"ticker": "VGT", "quantity": 5, "avg_cost_basis": 400})
    assert create_vgt.status_code == 200
    body = create_vgt.json()
    assert len(body["positions"]) == 2
    assert body["summary"]["total_cost_basis"] == 3500.0
    assert body["summary"]["total_market_value"] == 4250.0
    assert body["summary"]["total_unrealized_gain_loss"] == 750.0
    assert {row["ticker"] for row in body["positions"]} == {"AAPL", "VGT"}

    update_vgt = client.put("/portfolio/VGT", json={"quantity": 6, "avg_cost_basis": 410})
    assert update_vgt.status_code == 200
    updated = update_vgt.json()
    position = next(row for row in updated["positions"] if row["ticker"] == "VGT")
    assert position["quantity"] == 6.0
    assert position["avg_cost_basis"] == 410.0

    delete_aapl = client.delete("/portfolio/AAPL")
    assert delete_aapl.status_code == 200
    remaining = delete_aapl.json()
    assert len(remaining["positions"]) == 1
    assert remaining["positions"][0]["ticker"] == "VGT"


def test_portfolio_overview_reports_unpriced_positions(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        db.add(Company(ticker="VGT", name="VGT ETF", asset_type="etf"))
        db.commit()

    monkeypatch.setattr(portfolio_router, "fetch_alpha_quotes", lambda tickers: {})

    create = client.post("/portfolio", json={"ticker": "VGT", "quantity": 5, "avg_cost_basis": 400})
    assert create.status_code == 200
    body = create.json()
    assert body["summary"]["total_cost_basis"] == 2000.0
    assert body["summary"]["total_market_value"] is None
    assert body["summary"]["has_unpriced_positions"] is True
    assert body["positions"][0]["price_status"] == "unavailable"
