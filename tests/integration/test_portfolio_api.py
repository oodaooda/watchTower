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


def test_create_update_delete_duplicate_portfolio_positions(monkeypatch):
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
    assert len(body["groups"]) == 1
    assert body["summary"]["total_market_value"] == 2000.0

    create_vgt = client.post("/portfolio", json={"ticker": "VGT", "quantity": 5, "avg_cost_basis": 400})
    assert create_vgt.status_code == 200
    body = create_vgt.json()
    assert len(body["positions"]) == 2
    assert body["summary"]["total_cost_basis"] == 3500.0
    assert body["summary"]["total_market_value"] == 4250.0
    assert body["summary"]["total_unrealized_gain_loss"] == 750.0
    assert {row["ticker"] for row in body["positions"]} == {"AAPL", "VGT"}

    create_vgt_lot2 = client.post("/portfolio", json={"ticker": "VGT", "quantity": 2, "avg_cost_basis": 420})
    assert create_vgt_lot2.status_code == 200
    duplicated = create_vgt_lot2.json()
    assert len(duplicated["positions"]) == 3
    assert len([row for row in duplicated["positions"] if row["ticker"] == "VGT"]) == 2
    assert len(duplicated["groups"]) == 2
    vgt_group = next(row for row in duplicated["groups"] if row["ticker"] == "VGT")
    assert vgt_group["lot_count"] == 2
    assert vgt_group["total_quantity"] == 7.0

    vgt_position = next(row for row in duplicated["positions"] if row["ticker"] == "VGT")
    update_vgt = client.put(f"/portfolio/{vgt_position['position_id']}", json={"quantity": 6, "avg_cost_basis": 410})
    assert update_vgt.status_code == 200
    updated = update_vgt.json()
    edited = next(row for row in updated["positions"] if row["position_id"] == vgt_position["position_id"])
    sibling = next(
        row for row in updated["positions"] if row["ticker"] == "VGT" and row["position_id"] != vgt_position["position_id"]
    )
    assert edited["quantity"] == 6.0
    assert edited["avg_cost_basis"] == 410.0
    assert sibling["quantity"] == 2.0

    aapl_position = next(row for row in updated["positions"] if row["ticker"] == "AAPL")
    delete_aapl = client.delete(f"/portfolio/{aapl_position['position_id']}")
    assert delete_aapl.status_code == 200
    remaining = delete_aapl.json()
    assert len(remaining["positions"]) == 2
    assert all(row["ticker"] == "VGT" for row in remaining["positions"])


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


def test_replace_import_replaces_existing_portfolio(monkeypatch):
    client, SessionLocal = _build_test_client()

    with SessionLocal() as db:
        db.add_all(
            [
                Company(ticker="AAPL", name="Apple Inc.", asset_type="equity"),
                Company(ticker="AMD", name="AMD", asset_type="equity"),
                Company(ticker="VGT", name="VGT ETF", asset_type="etf"),
            ]
        )
        db.commit()

    monkeypatch.setattr(
        portfolio_router,
        "fetch_alpha_quotes",
        lambda tickers: {
            "AMD": {"price": 200.0, "source": "alpha_vantage", "status": "live"},
            "VGT": {"price": 450.0, "source": "alpha_vantage", "status": "live"},
        },
    )

    assert client.post("/portfolio", json={"ticker": "AAPL", "quantity": 10, "avg_cost_basis": 150}).status_code == 200

    imported = client.post(
        "/portfolio/import",
        json={
            "replace_existing": True,
            "positions": [
                {"ticker": "AMD", "quantity": 26, "avg_cost_basis": 219.18},
                {"ticker": "AMD", "quantity": 10, "avg_cost_basis": 189.79},
                {"ticker": "VGT", "quantity": 509.913, "avg_cost_basis": 619.22},
            ],
        },
    )
    assert imported.status_code == 200
    body = imported.json()
    assert len(body["positions"]) == 3
    assert len(body["groups"]) == 2
    assert {row["ticker"] for row in body["positions"]} == {"AMD", "VGT"}
    assert all(row["entry_source"] == "import" for row in body["positions"])
    amd_group = next(row for row in body["groups"] if row["ticker"] == "AMD")
    assert amd_group["lot_count"] == 2
    assert amd_group["total_quantity"] == 36.0
