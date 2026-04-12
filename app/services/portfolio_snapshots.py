from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.models import AssetPriceDaily, PortfolioPosition, PortfolioSnapshotDaily


def _as_float(value) -> float:
    return float(value or 0.0)


def latest_portfolio_price_date(db: Session) -> Optional[date]:
    position_company_ids = select(PortfolioPosition.company_id)
    return db.scalar(
        select(func.max(AssetPriceDaily.price_date)).where(
            AssetPriceDaily.company_id.in_(position_company_ids)
        )
    )


def create_or_update_portfolio_snapshot(
    db: Session,
    *,
    snapshot_date: Optional[date] = None,
    source: str = "asset_price_daily",
) -> Optional[PortfolioSnapshotDaily]:
    positions = db.scalars(select(PortfolioPosition)).all()
    if not positions:
        return None

    effective_date = snapshot_date or latest_portfolio_price_date(db)
    if effective_date is None:
        return None

    price_rows = db.scalars(
        select(AssetPriceDaily).where(AssetPriceDaily.price_date == effective_date)
    ).all()
    price_by_company = {row.company_id: float(row.close_price) for row in price_rows}

    total_cost_basis = 0.0
    total_market_value = 0.0
    priced_positions = 0
    unpriced_positions = 0

    for position in positions:
        quantity = _as_float(position.quantity)
        avg_cost_basis = _as_float(position.avg_cost_basis)
        total_cost_basis += quantity * avg_cost_basis
        close_price = price_by_company.get(position.company_id)
        if close_price is None:
            unpriced_positions += 1
            continue
        priced_positions += 1
        total_market_value += quantity * close_price

    is_complete = unpriced_positions == 0
    market_value_value = total_market_value if is_complete else None
    gain = market_value_value - total_cost_basis if market_value_value is not None else None
    gain_pct = (gain / total_cost_basis) if gain is not None and total_cost_basis > 0 else None

    snapshot = db.scalar(
        select(PortfolioSnapshotDaily).where(PortfolioSnapshotDaily.snapshot_date == effective_date)
    )
    if not snapshot:
        snapshot = PortfolioSnapshotDaily(snapshot_date=effective_date)
        db.add(snapshot)

    snapshot.total_cost_basis = Decimal(str(total_cost_basis))
    snapshot.total_market_value = Decimal(str(market_value_value)) if market_value_value is not None else None
    snapshot.unrealized_gain_loss = Decimal(str(gain)) if gain is not None else None
    snapshot.unrealized_gain_loss_pct = Decimal(str(gain_pct)) if gain_pct is not None else None
    snapshot.is_complete = is_complete
    snapshot.priced_positions = priced_positions
    snapshot.unpriced_positions = unpriced_positions
    snapshot.source = source
    db.commit()
    db.refresh(snapshot)
    return snapshot


def load_portfolio_snapshots(db: Session) -> List[PortfolioSnapshotDaily]:
    return db.scalars(
        select(PortfolioSnapshotDaily).order_by(PortfolioSnapshotDaily.snapshot_date.asc())
    ).all()


def inferred_baseline_snapshot(
    db: Session,
    snapshots: Optional[List[PortfolioSnapshotDaily]] = None,
) -> Optional[Dict[str, float | int | str | bool | None]]:
    positions = db.scalars(select(PortfolioPosition)).all()
    if not positions:
        return None

    total_cost_basis = 0.0
    total_positions = 0
    for position in positions:
        quantity = _as_float(position.quantity)
        avg_cost_basis = _as_float(position.avg_cost_basis)
        total_cost_basis += quantity * avg_cost_basis
        total_positions += 1

    rows = snapshots if snapshots is not None else load_portfolio_snapshots(db)
    first_real_date = rows[0].snapshot_date if rows else None
    baseline_date = (first_real_date - timedelta(days=1)) if first_real_date else date.today()
    return {
        "snapshot_date": baseline_date.isoformat(),
        "total_cost_basis": total_cost_basis,
        "total_market_value": total_cost_basis,
        "unrealized_gain_loss": 0.0,
        "unrealized_gain_loss_pct": 0.0,
        "is_complete": True,
        "priced_positions": total_positions,
        "unpriced_positions": 0,
        "source": "initial_cost_basis_baseline",
        "is_inferred": True,
    }


def rebuild_portfolio_snapshots_from_dates(
    db: Session,
    snapshot_dates: List[date],
    *,
    source: str = "asset_price_daily_backfill",
) -> Dict[str, object]:
    created_or_updated = 0
    latest_complete_snapshot_date: Optional[str] = None

    for snapshot_date in snapshot_dates:
        snapshot = create_or_update_portfolio_snapshot(db, snapshot_date=snapshot_date, source=source)
        if snapshot:
            created_or_updated += 1
            latest_complete_snapshot_date = snapshot.snapshot_date.isoformat()

    return {
        "complete_snapshot_dates": created_or_updated,
        "latest_complete_snapshot_date": latest_complete_snapshot_date,
    }


def _period_change(
    snapshots: List[PortfolioSnapshotDaily],
    *,
    cutoff: date,
) -> Optional[Dict[str, float | str | None]]:
    valued = [row for row in snapshots if row.total_market_value is not None]
    if len(valued) < 2:
        return None
    latest = valued[-1]
    baseline = next((row for row in valued if row.snapshot_date >= cutoff), valued[0])
    latest_value = float(latest.total_market_value)
    baseline_value = float(baseline.total_market_value)
    change = latest_value - baseline_value
    change_pct = (change / baseline_value) if baseline_value else None
    return {
        "start_date": baseline.snapshot_date.isoformat(),
        "end_date": latest.snapshot_date.isoformat(),
        "change": change,
        "change_pct": change_pct,
    }


def snapshot_history_summary(snapshots: List[PortfolioSnapshotDaily]) -> Dict[str, Optional[Dict[str, float | str | None]]]:
    valued = [row for row in snapshots if row.total_market_value is not None]
    if len(valued) < 2:
        return {"1d": None, "1m": None, "ytd": None, "1y": None}

    latest = valued[-1]
    previous = valued[-2]
    latest_value = float(latest.total_market_value)
    previous_value = float(previous.total_market_value)
    day_change = latest_value - previous_value
    one_day = {
        "start_date": previous.snapshot_date.isoformat(),
        "end_date": latest.snapshot_date.isoformat(),
        "change": day_change,
        "change_pct": (day_change / previous_value) if previous_value else None,
    }
    return {
        "1d": one_day,
        "1m": _period_change(valued, cutoff=latest.snapshot_date - timedelta(days=32)),
        "ytd": _period_change(valued, cutoff=date(latest.snapshot_date.year, 1, 1)),
        "1y": _period_change(valued, cutoff=latest.snapshot_date - timedelta(days=366)),
    }
