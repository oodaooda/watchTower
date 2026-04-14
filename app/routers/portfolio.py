from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Company, PortfolioPosition
from app.core.schemas import (
    PortfolioImportRequest,
    PortfolioOverview,
    PortfolioPositionIn,
    PortfolioPositionItem,
    PortfolioTickerGroupItem,
    PortfolioPositionUpdate,
    PortfolioPriceBackfillItem,
    PortfolioPriceBackfillResult,
    PortfolioSnapshotHistory,
    PortfolioSnapshotItem,
    PortfolioSummary,
)
from app.services.portfolio_snapshots import (
    create_or_update_portfolio_snapshot,
    inferred_baseline_snapshot,
    load_portfolio_snapshots,
    rebuild_portfolio_snapshots_from_dates,
    snapshot_history_summary,
)
from app.services.assets import find_or_create_asset, normalize_symbol, resolve_asset
from app.services.price_history import backfill_portfolio_daily_history, complete_portfolio_price_dates
from app.services.quotes import fetch_alpha_quotes, resolve_current_quote

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class PortfolioPriceBackfillRequest(BaseModel):
    force_refresh: bool = True
    sleep_seconds: float = Field(default=12.0, ge=0.0, le=60.0)


def _serialize_snapshot_history(db: Session) -> PortfolioSnapshotHistory:
    snapshots = load_portfolio_snapshots(db)
    baseline = inferred_baseline_snapshot(db, snapshots)
    items = []
    if baseline:
        items.append(
            PortfolioSnapshotItem(
                snapshot_date=str(baseline["snapshot_date"]),
                total_cost_basis=float(baseline["total_cost_basis"]),
                total_market_value=float(baseline["total_market_value"]) if baseline["total_market_value"] is not None else None,
                unrealized_gain_loss=float(baseline["unrealized_gain_loss"]) if baseline["unrealized_gain_loss"] is not None else None,
                unrealized_gain_loss_pct=float(baseline["unrealized_gain_loss_pct"]) if baseline["unrealized_gain_loss_pct"] is not None else None,
                is_complete=bool(baseline["is_complete"]),
                priced_positions=int(baseline["priced_positions"]),
                unpriced_positions=int(baseline["unpriced_positions"]),
                source=str(baseline["source"]),
                is_inferred=bool(baseline["is_inferred"]),
            )
        )
    return PortfolioSnapshotHistory(
        snapshots=items + [
            PortfolioSnapshotItem(
                snapshot_date=row.snapshot_date.isoformat(),
                total_cost_basis=float(row.total_cost_basis),
                total_market_value=float(row.total_market_value) if row.total_market_value is not None else None,
                unrealized_gain_loss=float(row.unrealized_gain_loss) if row.unrealized_gain_loss is not None else None,
                unrealized_gain_loss_pct=float(row.unrealized_gain_loss_pct) if row.unrealized_gain_loss_pct is not None else None,
                is_complete=bool(row.is_complete),
                priced_positions=int(row.priced_positions or 0),
                unpriced_positions=int(row.unpriced_positions or 0),
                source=row.source or "asset_price_daily",
                is_inferred=False,
            )
            for row in snapshots
        ],
        summary=snapshot_history_summary(snapshots),
    )


def _validate_position_fields(quantity: float | None, avg_cost_basis: float | None) -> None:
    if quantity is not None and quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
    if avg_cost_basis is not None and avg_cost_basis < 0:
        raise HTTPException(status_code=400, detail="Average cost basis must be zero or greater")


def _normalize_entry_source(value: str | None) -> str:
    normalized = (value or "manual").strip().lower()
    if normalized not in {"manual", "import"}:
        return "manual"
    return normalized


def _group_portfolio_items(items: List[PortfolioPositionItem]) -> List[PortfolioTickerGroupItem]:
    grouped: Dict[tuple[int, str], List[PortfolioPositionItem]] = defaultdict(list)
    for item in items:
        grouped[(item.company_id, item.ticker)].append(item)

    groups: List[PortfolioTickerGroupItem] = []
    for (_company_id, _ticker), bucket in sorted(grouped.items(), key=lambda entry: entry[0][1]):
        first = bucket[0]
        total_quantity = sum(item.quantity for item in bucket)
        total_cost_basis = sum(item.total_cost_basis for item in bucket)
        weighted_avg_cost_basis = (total_cost_basis / total_quantity) if total_quantity > 0 else 0.0
        market_values = [item.market_value for item in bucket]
        market_value = None if any(value is None for value in market_values) else sum(value or 0.0 for value in market_values)
        gain = None if market_value is None else market_value - total_cost_basis
        gain_pct = (gain / total_cost_basis) if (gain is not None and total_cost_basis > 0) else None
        price_status = "unavailable" if any(item.price_status == "unavailable" for item in bucket) else bucket[0].price_status
        price_source = bucket[0].price_source
        current_price = None if any(item.current_price is None for item in bucket) else bucket[0].current_price
        groups.append(
            PortfolioTickerGroupItem(
                ticker=first.ticker,
                company_id=first.company_id,
                asset_type=first.asset_type,
                name=first.name,
                industry=first.industry,
                lot_count=len(bucket),
                total_quantity=total_quantity,
                weighted_avg_cost_basis=weighted_avg_cost_basis,
                total_cost_basis=total_cost_basis,
                current_price=current_price,
                market_value=market_value,
                unrealized_gain_loss=gain,
                unrealized_gain_loss_pct=gain_pct,
                portfolio_weight=None,
                price_status=price_status,
                price_source=price_source,
            )
        )
    return groups


def _serialize_portfolio_positions(db: Session, positions: List[PortfolioPosition]) -> PortfolioOverview:
    quote_map = fetch_alpha_quotes(position.company.ticker for position in positions if position.company)
    items: List[PortfolioPositionItem] = []
    has_unpriced_positions = False
    live_live_positions = 0
    live_cached_positions = 0
    live_unavailable_positions = 0

    for position in positions:
        asset = position.company
        if not asset:
            continue
        quote = resolve_current_quote(db, asset, quote_map)
        quantity = float(position.quantity)
        avg_cost_basis = float(position.avg_cost_basis)
        total_cost_basis = quantity * avg_cost_basis
        current_price = quote.get("price")
        market_value = current_price * quantity if current_price is not None else None
        gain = market_value - total_cost_basis if market_value is not None else None
        gain_pct = (gain / total_cost_basis) if (gain is not None and total_cost_basis not in (0, None)) else None
        if market_value is None:
            has_unpriced_positions = True
        status = str(quote.get("status") or "unavailable")
        if status == "live":
            live_live_positions += 1
        elif status == "cached":
            live_cached_positions += 1
        else:
            live_unavailable_positions += 1
        items.append(
            PortfolioPositionItem(
                position_id=position.id,
                company_id=asset.id,
                ticker=asset.ticker,
                asset_type=getattr(asset, "asset_type", None) or "equity",
                name=asset.name,
                industry=asset.industry_name,
                quantity=quantity,
                avg_cost_basis=avg_cost_basis,
                total_cost_basis=total_cost_basis,
                current_price=current_price,
                market_value=market_value,
                unrealized_gain_loss=gain,
                unrealized_gain_loss_pct=gain_pct,
                portfolio_weight=None,
                price_status=status,
                price_source=quote.get("source"),
                entry_source=_normalize_entry_source(getattr(position, "entry_source", None)),
                notes=position.notes,
            )
        )

    groups = _group_portfolio_items(items)
    total_cost_basis = sum(item.total_cost_basis for item in items)
    live_priced_positions = sum(1 for item in items if item.market_value is not None)
    live_unpriced_positions = sum(1 for item in items if item.market_value is None)
    live_total_market_value = sum(item.market_value or 0.0 for item in items if item.market_value is not None)
    if live_priced_positions == 0:
        live_total_market_value = None
    total_market_value = None if has_unpriced_positions else sum(item.market_value or 0.0 for item in items)
    live_total_gain = None if live_total_market_value is None else live_total_market_value - total_cost_basis
    total_gain = None if total_market_value is None else total_market_value - total_cost_basis
    live_total_gain_pct = None
    if live_total_gain is not None and total_cost_basis > 0:
        live_total_gain_pct = live_total_gain / total_cost_basis
    total_gain_pct = None
    if total_gain is not None and total_cost_basis > 0:
        total_gain_pct = total_gain / total_cost_basis

    if total_market_value not in (None, 0):
        for item in items:
            if item.market_value is not None:
                item.portfolio_weight = item.market_value / total_market_value
        for group in groups:
            if group.market_value is not None:
                group.portfolio_weight = group.market_value / total_market_value

    return PortfolioOverview(
        summary=PortfolioSummary(
            total_cost_basis=total_cost_basis,
            total_market_value=total_market_value,
            total_unrealized_gain_loss=total_gain,
            total_unrealized_gain_loss_pct=total_gain_pct,
            live_total_market_value=live_total_market_value,
            live_total_unrealized_gain_loss=live_total_gain,
            live_total_unrealized_gain_loss_pct=live_total_gain_pct,
            live_total_is_complete=not has_unpriced_positions,
            live_coverage_pct=(live_priced_positions / len(items)) if items else None,
            live_priced_positions=live_priced_positions,
            live_unpriced_positions=live_unpriced_positions,
            live_live_positions=live_live_positions,
            live_cached_positions=live_cached_positions,
            live_unavailable_positions=live_unavailable_positions,
            has_unpriced_positions=has_unpriced_positions,
            priced_positions=live_priced_positions,
            unpriced_positions=live_unpriced_positions,
            total_positions=len(items),
            grouped_assets=len(groups),
        ),
        positions=items,
        groups=groups,
    )


def _load_positions(db: Session) -> List[PortfolioPosition]:
    return db.scalars(
        select(PortfolioPosition)
        .join(PortfolioPosition.company)
        .order_by(Company.ticker.asc(), PortfolioPosition.created_at.asc(), PortfolioPosition.id.asc())
    ).all()


@router.get("", response_model=PortfolioOverview)
def get_portfolio(db: Session = Depends(get_db)):
    return _serialize_portfolio_positions(db, _load_positions(db))


@router.get("/snapshots", response_model=PortfolioSnapshotHistory)
def get_portfolio_snapshots(db: Session = Depends(get_db)):
    return _serialize_snapshot_history(db)


@router.post("/snapshots/run", response_model=PortfolioSnapshotHistory)
def run_portfolio_snapshot(db: Session = Depends(get_db)):
    create_or_update_portfolio_snapshot(db)
    return _serialize_snapshot_history(db)


@router.post("/prices/backfill", response_model=PortfolioPriceBackfillResult)
def backfill_portfolio_prices(payload: PortfolioPriceBackfillRequest, db: Session = Depends(get_db)):
    result = backfill_portfolio_daily_history(
        db,
        force_refresh=payload.force_refresh,
        sleep_seconds=payload.sleep_seconds,
    )
    snapshot_result = rebuild_portfolio_snapshots_from_dates(
        db,
        complete_portfolio_price_dates(db),
    )
    return PortfolioPriceBackfillResult(
        total_assets=int(result["total_assets"]),
        attempted_assets=int(result["attempted_assets"]),
        succeeded_assets=int(result["succeeded_assets"]),
        failed_assets=int(result["failed_assets"]),
        complete_snapshot_dates=int(snapshot_result["complete_snapshot_dates"]),
        latest_complete_snapshot_date=snapshot_result["latest_complete_snapshot_date"],
        items=[
            PortfolioPriceBackfillItem(
                ticker=str(item["ticker"]),
                status=str(item["status"]),
                history_rows=int(item["history_rows"]),
                latest_price_date=item["latest_price_date"],
                error=item["error"],
            )
            for item in result["items"]
        ],
    )


@router.post("", response_model=PortfolioOverview)
def add_portfolio_position(payload: PortfolioPositionIn, db: Session = Depends(get_db)):
    ticker = normalize_symbol(payload.ticker)
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")
    _validate_position_fields(payload.quantity, payload.avg_cost_basis)

    asset = find_or_create_asset(db, ticker, track_reason="portfolio_asset")
    if not asset:
        raise HTTPException(status_code=404, detail="Tracked asset not found")

    db.add(
        PortfolioPosition(
            company_id=asset.id,
            quantity=payload.quantity,
            avg_cost_basis=payload.avg_cost_basis,
            entry_source=_normalize_entry_source(payload.entry_source),
            notes=payload.notes,
        )
    )
    db.commit()
    return _serialize_portfolio_positions(db, _load_positions(db))


@router.put("/{position_id}", response_model=PortfolioOverview)
def update_portfolio_position(position_id: int, payload: PortfolioPositionUpdate, db: Session = Depends(get_db)):
    position = db.execute(
        select(PortfolioPosition).where(PortfolioPosition.id == position_id)
    ).scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Portfolio position not found")

    _validate_position_fields(payload.quantity, payload.avg_cost_basis)
    if payload.quantity is not None:
        position.quantity = payload.quantity
    if payload.avg_cost_basis is not None:
        position.avg_cost_basis = payload.avg_cost_basis
    if payload.notes is not None:
        position.notes = payload.notes
    db.commit()
    return _serialize_portfolio_positions(db, _load_positions(db))


@router.delete("/{position_id}", response_model=PortfolioOverview)
def delete_portfolio_position(position_id: int, db: Session = Depends(get_db)):
    position = db.execute(
        select(PortfolioPosition).where(PortfolioPosition.id == position_id)
    ).scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Portfolio position not found")

    db.delete(position)
    db.commit()
    return _serialize_portfolio_positions(db, _load_positions(db))


@router.post("/import", response_model=PortfolioOverview)
def import_portfolio_positions(payload: PortfolioImportRequest, db: Session = Depends(get_db)):
    rows = payload.positions or []
    if not rows:
        raise HTTPException(status_code=400, detail="At least one portfolio row is required")

    resolved_rows = []
    errors = []
    for idx, row in enumerate(rows, start=1):
        ticker = normalize_symbol(row.ticker)
        try:
            _validate_position_fields(row.quantity, row.avg_cost_basis)
        except HTTPException as exc:
            errors.append({"row": idx, "ticker": ticker or row.ticker, "error": exc.detail})
            continue
        if not ticker:
            errors.append({"row": idx, "ticker": row.ticker, "error": "Ticker is required"})
            continue
        asset = find_or_create_asset(db, ticker, track_reason="portfolio_asset")
        if not asset:
            errors.append({"row": idx, "ticker": ticker, "error": "Tracked asset not found"})
            continue
        resolved_rows.append(
            {
                "company_id": asset.id,
                "quantity": row.quantity,
                "avg_cost_basis": row.avg_cost_basis,
                "notes": row.notes,
            }
        )

    if errors:
        raise HTTPException(status_code=400, detail={"message": "Portfolio import validation failed", "errors": errors})

    if payload.replace_existing:
        db.query(PortfolioPosition).delete()
        db.flush()

    for row in resolved_rows:
        db.add(
            PortfolioPosition(
                company_id=row["company_id"],
                quantity=row["quantity"],
                avg_cost_basis=row["avg_cost_basis"],
                entry_source="import",
                notes=row["notes"],
            )
        )
    db.commit()
    return _serialize_portfolio_positions(db, _load_positions(db))
