from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.core.models import Company, PortfolioPosition
from app.routers.portfolio import _serialize_portfolio_positions


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


def test_portfolio_math_calculates_market_value_and_gain(monkeypatch):
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
            ]
        )
        db.commit()
        positions = db.query(PortfolioPosition).order_by(PortfolioPosition.id.asc()).all()

        monkeypatch.setattr(
            "app.routers.portfolio.fetch_alpha_quotes",
            lambda tickers: {
                "AAPL": {"price": 200.0, "source": "alpha_vantage", "status": "live"},
                "VGT": {"price": 450.0, "source": "alpha_vantage", "status": "live"},
            },
        )

        overview = _serialize_portfolio_positions(db, positions)
        assert overview.summary.total_cost_basis == 3500.0
        assert overview.summary.total_market_value == 4250.0
        assert overview.summary.total_unrealized_gain_loss == 750.0
        assert overview.summary.total_unrealized_gain_loss_pct == 750.0 / 3500.0
        assert overview.summary.has_unpriced_positions is False
        assert len(overview.positions) == 2
        assert len(overview.groups) == 2
        assert round(sum(item.portfolio_weight or 0.0 for item in overview.positions), 6) == 1.0


def test_portfolio_summary_is_explicit_when_quote_is_missing(monkeypatch):
    SessionLocal = _session_local()

    with SessionLocal() as db:
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add(vgt)
        db.commit()
        db.refresh(vgt)
        db.add(PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=400))
        db.commit()
        positions = db.query(PortfolioPosition).all()

        monkeypatch.setattr("app.routers.portfolio.fetch_alpha_quotes", lambda tickers: {})

        overview = _serialize_portfolio_positions(db, positions)
        assert overview.summary.total_cost_basis == 2000.0
        assert overview.summary.total_market_value is None
        assert overview.summary.total_unrealized_gain_loss is None
        assert overview.summary.total_unrealized_gain_loss_pct is None
        assert overview.summary.has_unpriced_positions is True
        assert overview.summary.unpriced_positions == 1
        assert overview.positions[0].price_status == "unavailable"
        assert overview.positions[0].market_value is None


def test_portfolio_groups_aggregate_duplicate_lots(monkeypatch):
    SessionLocal = _session_local()

    with SessionLocal() as db:
        vgt = Company(ticker="VGT", name="VGT ETF", asset_type="etf")
        db.add(vgt)
        db.commit()
        db.refresh(vgt)
        db.add_all(
            [
                PortfolioPosition(company_id=vgt.id, quantity=10, avg_cost_basis=400),
                PortfolioPosition(company_id=vgt.id, quantity=5, avg_cost_basis=500),
            ]
        )
        db.commit()
        positions = db.query(PortfolioPosition).order_by(PortfolioPosition.id.asc()).all()

        monkeypatch.setattr(
            "app.routers.portfolio.fetch_alpha_quotes",
            lambda tickers: {
                "VGT": {"price": 450.0, "source": "alpha_vantage", "status": "live"},
            },
        )

        overview = _serialize_portfolio_positions(db, positions)
        assert len(overview.positions) == 2
        assert len(overview.groups) == 1
        group = overview.groups[0]
        assert group.ticker == "VGT"
        assert group.lot_count == 2
        assert group.total_quantity == 15.0
        assert group.total_cost_basis == 6500.0
        assert round(group.weighted_avg_cost_basis, 6) == round(6500.0 / 15.0, 6)
        assert group.market_value == 6750.0
        assert group.unrealized_gain_loss == 250.0
