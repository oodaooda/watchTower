from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Company, PortfolioPosition
from app.core.schemas import (
    PortfolioOverview,
    PortfolioPositionIn,
    PortfolioPositionItem,
    PortfolioPositionUpdate,
    PortfolioSummary,
)
from app.services.assets import find_or_create_asset, normalize_symbol, resolve_asset
from app.services.quotes import fetch_alpha_quotes, resolve_current_quote

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _validate_position_fields(quantity: float | None, avg_cost_basis: float | None) -> None:
    if quantity is not None and quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero")
    if avg_cost_basis is not None and avg_cost_basis < 0:
        raise HTTPException(status_code=400, detail="Average cost basis must be zero or greater")


def _serialize_portfolio_positions(db: Session, positions: List[PortfolioPosition]) -> PortfolioOverview:
    quote_map = fetch_alpha_quotes(position.company.ticker for position in positions if position.company)
    items: List[PortfolioPositionItem] = []
    has_unpriced_positions = False

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
                price_status=str(quote.get("status") or "unavailable"),
                price_source=quote.get("source"),
                notes=position.notes,
            )
        )

    total_cost_basis = sum(item.total_cost_basis for item in items)
    total_market_value = None if has_unpriced_positions else sum(item.market_value or 0.0 for item in items)
    total_gain = None if total_market_value is None else total_market_value - total_cost_basis
    total_gain_pct = None
    if total_gain is not None and total_cost_basis > 0:
        total_gain_pct = total_gain / total_cost_basis

    if total_market_value not in (None, 0):
        for item in items:
            if item.market_value is not None:
                item.portfolio_weight = item.market_value / total_market_value

    return PortfolioOverview(
        summary=PortfolioSummary(
            total_cost_basis=total_cost_basis,
            total_market_value=total_market_value,
            total_unrealized_gain_loss=total_gain,
            total_unrealized_gain_loss_pct=total_gain_pct,
            has_unpriced_positions=has_unpriced_positions,
            priced_positions=sum(1 for item in items if item.market_value is not None),
            unpriced_positions=sum(1 for item in items if item.market_value is None),
        ),
        positions=items,
    )


def _load_positions(db: Session) -> List[PortfolioPosition]:
    return db.scalars(
        select(PortfolioPosition)
        .join(PortfolioPosition.company)
        .order_by(Company.ticker.asc())
    ).all()


@router.get("", response_model=PortfolioOverview)
def get_portfolio(db: Session = Depends(get_db)):
    return _serialize_portfolio_positions(db, _load_positions(db))


@router.post("", response_model=PortfolioOverview)
def add_portfolio_position(payload: PortfolioPositionIn, db: Session = Depends(get_db)):
    ticker = normalize_symbol(payload.ticker)
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")
    _validate_position_fields(payload.quantity, payload.avg_cost_basis)

    asset = find_or_create_asset(db, ticker, track_reason="portfolio_asset")
    if not asset:
        raise HTTPException(status_code=404, detail="Tracked asset not found")

    existing = db.execute(
        select(PortfolioPosition).where(PortfolioPosition.company_id == asset.id)
    ).scalar_one_or_none()
    if existing:
        existing.quantity = payload.quantity
        existing.avg_cost_basis = payload.avg_cost_basis
        existing.notes = payload.notes
    else:
        db.add(
            PortfolioPosition(
                company_id=asset.id,
                quantity=payload.quantity,
                avg_cost_basis=payload.avg_cost_basis,
                notes=payload.notes,
            )
        )
    db.commit()
    return _serialize_portfolio_positions(db, _load_positions(db))


@router.put("/{ticker}", response_model=PortfolioOverview)
def update_portfolio_position(ticker: str, payload: PortfolioPositionUpdate, db: Session = Depends(get_db)):
    asset = resolve_asset(db, ticker)
    if not asset:
        raise HTTPException(status_code=404, detail="Tracked asset not found")

    position = db.execute(
        select(PortfolioPosition).where(PortfolioPosition.company_id == asset.id)
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


@router.delete("/{ticker}", response_model=PortfolioOverview)
def delete_portfolio_position(ticker: str, db: Session = Depends(get_db)):
    asset = resolve_asset(db, ticker)
    if not asset:
        raise HTTPException(status_code=404, detail="Tracked asset not found")

    position = db.execute(
        select(PortfolioPosition).where(PortfolioPosition.company_id == asset.id)
    ).scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Portfolio position not found")

    db.delete(position)
    db.commit()
    return _serialize_portfolio_positions(db, _load_positions(db))
