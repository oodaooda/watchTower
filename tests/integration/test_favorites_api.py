from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.models import Company, FavoriteCompany
from app.routers import favorites as favorites_router


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
    app.include_router(favorites_router.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), SessionLocal


def test_add_list_and_remove_etf_favorite(monkeypatch):
    client, SessionLocal = _build_test_client()

    monkeypatch.setattr(
        "app.services.assets.fetch_alpha_asset_overview",
        lambda symbol: {
            "Symbol": symbol,
            "Name": "Vanguard Information Technology ETF",
            "AssetType": "ETF",
            "Exchange": "NYSE ARCA",
            "Currency": "USD",
            "Description": "An exchange traded fund focused on information technology equities.",
        },
    )
    monkeypatch.setattr(
        favorites_router,
        "fetch_alpha_quotes",
        lambda tickers: {
            "VGT": {
                "price": 612.34,
                "previous_close": 600.0,
                "change_percent": 0.0205,
                "source": "alpha_vantage",
            }
        },
    )

    create = client.post("/favorites", json={"ticker": "VGT"})
    assert create.status_code == 200
    created = create.json()
    assert created["ticker"] == "VGT"
    assert created["asset_type"] == "etf"
    assert created["price"] == 612.34
    assert created["pe"] is None

    listing = client.get("/favorites")
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    assert rows[0]["ticker"] == "VGT"
    assert rows[0]["asset_type"] == "etf"

    with SessionLocal() as db:
        asset = db.query(Company).filter(Company.ticker == "VGT").one()
        assert asset.asset_type == "etf"
        assert db.query(FavoriteCompany).count() == 1

    delete = client.delete("/favorites/VGT")
    assert delete.status_code == 200
    assert delete.json()["ticker"] == "VGT"

    listing_after = client.get("/favorites")
    assert listing_after.status_code == 200
    assert listing_after.json() == []
