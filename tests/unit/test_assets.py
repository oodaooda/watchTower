from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.core.models import Company, FavoriteCompany
from app.routers.favorites import _serialize_favorite
from app.services.assets import classify_asset_type, fetch_alpha_asset_overview


def test_classify_asset_type_detects_etf_from_explicit_field():
    asset_type = classify_asset_type(
        {"Symbol": "VGT", "Name": "Vanguard Information Technology ETF", "AssetType": "ETF"}
    )
    assert asset_type == "etf"


def test_classify_asset_type_defaults_to_equity_for_operating_company():
    asset_type = classify_asset_type(
        {
            "Symbol": "AAPL",
            "Name": "Apple Inc.",
            "Description": "Apple designs and sells consumer electronics and software.",
            "AssetType": "Stock",
        }
    )
    assert asset_type == "equity"


def test_fetch_alpha_asset_overview_falls_back_to_etf_profile(monkeypatch):
    monkeypatch.setattr("app.services.assets.settings.alpha_vantage_api_key", "demo")

    def fake_request(function_name: str, symbol: str):
        if function_name == "OVERVIEW":
            return {}
        if function_name == "ETF_PROFILE":
            return {
                "net_assets": "126500000000",
                "sectors": [{"sector": "INFORMATION TECHNOLOGY", "weight": "0.985"}],
                "holdings": [{"symbol": "NVDA", "description": "NVIDIA CORP", "weight": "0.1807"}],
            }
        return None

    monkeypatch.setattr("app.services.assets._alpha_request", fake_request)

    overview = fetch_alpha_asset_overview("VGT")
    assert overview is not None
    assert overview["Symbol"] == "VGT"
    assert overview["AssetType"] == "ETF"
    assert overview["Industry"] == "INFORMATION TECHNOLOGY"


def test_serialize_favorite_allows_etf_without_fundamentals():
    engine = create_engine(
        "sqlite+pysqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        asset = Company(
            ticker="VGT",
            name="Vanguard Information Technology ETF",
            asset_type="etf",
            exchange="NYSE ARCA",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        favorite = FavoriteCompany(company_id=asset.id, sort_order=1)
        db.add(favorite)
        db.commit()
        db.refresh(favorite)

        item = _serialize_favorite(
            db,
            favorite,
            {"VGT": {"price": 612.34, "previous_close": 600.0, "change_percent": 0.0205, "source": "alpha_vantage"}},
        )

        assert item is not None
        assert item.asset_type == "etf"
        assert item.ticker == "VGT"
        assert item.price == 612.34
        assert item.pe is None
        assert item.eps is None
        assert item.market_cap is None
