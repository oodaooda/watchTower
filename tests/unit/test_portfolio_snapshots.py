from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.core.models import AssetPriceDaily, Company, PortfolioPosition
from app.services.portfolio_snapshots import (
    create_or_update_portfolio_snapshot,
    load_portfolio_snapshots,
    snapshot_history_summary,
)


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


def test_portfolio_snapshot_calculates_totals_from_eod_closes():
    SessionLocal = _session_local()

    with SessionLocal() as db:
        aapl = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity")
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add_all([aapl, vgt])
        db.commit()
        db.refresh(aapl)
        db.refresh(vgt)
        db.add_all(
            [
                PortfolioPosition(company_id=aapl.id, quantity=10, avg_cost_basis=150),
                PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=400),
                AssetPriceDaily(company_id=aapl.id, price_date=date(2026, 4, 9), close_price=200),
                AssetPriceDaily(company_id=vgt.id, price_date=date(2026, 4, 9), close_price=450),
            ]
        )
        db.commit()

        snapshot = create_or_update_portfolio_snapshot(db, snapshot_date=date(2026, 4, 9))
        assert snapshot is not None
        assert float(snapshot.total_cost_basis) == 3500.0
        assert float(snapshot.total_market_value) == 4250.0
        assert float(snapshot.unrealized_gain_loss) == 750.0
        assert snapshot.is_complete is True


def test_portfolio_snapshot_marks_missing_prices_incomplete():
    SessionLocal = _session_local()

    with SessionLocal() as db:
        aapl = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity")
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add_all([aapl, vgt])
        db.commit()
        db.refresh(aapl)
        db.refresh(vgt)
        db.add_all(
            [
                PortfolioPosition(company_id=aapl.id, quantity=10, avg_cost_basis=150),
                PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=400),
                AssetPriceDaily(company_id=aapl.id, price_date=date(2026, 4, 9), close_price=200),
            ]
        )
        db.commit()

        snapshot = create_or_update_portfolio_snapshot(db, snapshot_date=date(2026, 4, 9))
        assert snapshot is not None
        assert snapshot.total_market_value is None
        assert snapshot.unrealized_gain_loss is None
        assert snapshot.unrealized_gain_loss_pct is None
        assert snapshot.is_complete is False
        assert snapshot.priced_positions == 1
        assert snapshot.unpriced_positions == 1


def test_snapshot_history_summary_calculates_period_changes():
    SessionLocal = _session_local()

    with SessionLocal() as db:
        asset = Company(ticker="AAPL", name="Apple Inc.", asset_type="equity")
        db.add(asset)
        db.commit()
        db.refresh(asset)
        db.add(PortfolioPosition(company_id=asset.id, quantity=10, avg_cost_basis=100))
        for snapshot_date, close in (
            (date(2026, 1, 2), 100),
            (date(2026, 3, 10), 110),
            (date(2026, 4, 8), 120),
            (date(2026, 4, 9), 125),
        ):
            db.add(AssetPriceDaily(company_id=asset.id, price_date=snapshot_date, close_price=close))
            db.commit()
            create_or_update_portfolio_snapshot(db, snapshot_date=snapshot_date)

        summary = snapshot_history_summary(load_portfolio_snapshots(db))
        assert summary["1d"]["change"] == 50.0
        assert summary["1m"]["change"] == 150.0
        assert summary["ytd"]["change"] == 250.0
