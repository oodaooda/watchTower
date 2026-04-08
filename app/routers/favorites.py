from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import (
    Company,
    FavoriteCompany,
    FinancialAnnual,
    MetricsAnnual,
    PriceAnnual,
)
from app.core.schemas import FavoriteCompanyItem
from app.services.assets import find_or_create_asset, normalize_symbol, resolve_asset
from app.services.quotes import coalesce, fetch_alpha_quotes, ratio, resolve_current_quote, to_float

router = APIRouter(prefix="/favorites", tags=["favorites"])


class FavoriteCreate(BaseModel):
    ticker: str
    notes: Optional[str] = None


def _resolve_company(db: Session, ticker: str) -> Company | None:
    return resolve_asset(db, ticker)


def _serialize_favorite(
    db: Session,
    fav: FavoriteCompany,
    quote_map: Dict[str, Dict[str, float | None]] | None = None,
) -> FavoriteCompanyItem | None:
    co = fav.company
    if not co:
        return None
    metrics = db.scalars(
        select(MetricsAnnual)
        .where(MetricsAnnual.company_id == co.id)
        .order_by(MetricsAnnual.fiscal_year.desc())
        .limit(1)
    ).first()
    financial = db.scalars(
        select(FinancialAnnual)
        .where(FinancialAnnual.company_id == co.id)
        .order_by(FinancialAnnual.fiscal_year.desc())
        .limit(1)
    ).first()
    price_row = db.scalars(
        select(PriceAnnual)
        .where(PriceAnnual.company_id == co.id)
        .order_by(PriceAnnual.fiscal_year.desc())
        .limit(1)
    ).first()

    quote = quote_map.get(co.ticker.upper()) if quote_map else None

    price = coalesce(quote and quote.get("price"), to_float(getattr(price_row, "close_price", None)))
    prev_close = coalesce(
        quote and quote.get("previous_close"),
        to_float(getattr(price_row, "close_price", None)),
    )
    if quote and quote.get("change_percent") is not None:
        change_pct = quote.get("change_percent")
    elif price is not None and prev_close not in (None, 0):
        change_pct = ratio(price - prev_close, prev_close)
    else:
        change_pct = None

    shares = to_float(getattr(financial, "shares_outstanding", None))
    eps = coalesce(
        to_float(getattr(metrics, "ttm_eps", None)),
        ratio(to_float(getattr(financial, "net_income", None)), shares),
    )
    pe = coalesce(
        to_float(getattr(metrics, "pe_ttm", None)),
        ratio(price, eps) if price is not None and eps not in (None, 0) else None,
    )
    market_cap = price * shares if (price is not None and shares is not None) else None

    return FavoriteCompanyItem(
        company_id=co.id,
        ticker=co.ticker,
        asset_type=getattr(co, "asset_type", None) or "equity",
        name=co.name,
        industry=co.industry_name,
        price=price,
        change_percent=change_pct,
        pe=pe,
        eps=eps,
        market_cap=market_cap,
        notes=fav.notes,
        source=quote.get("source") if quote else "cached",
    )


@router.get("", response_model=List[FavoriteCompanyItem])
def list_favorites(db: Session = Depends(get_db)):
    favorites = db.scalars(
        select(FavoriteCompany)
        .join(FavoriteCompany.company)
        .order_by(FavoriteCompany.sort_order, FavoriteCompany.created_at)
    ).all()

    quotes = fetch_alpha_quotes(fav.company.ticker for fav in favorites if fav.company)

    items: List[FavoriteCompanyItem] = []
    for fav in favorites:
        serialized = _serialize_favorite(db, fav, quotes)
        if serialized:
            items.append(serialized)
    return items


@router.post("", response_model=FavoriteCompanyItem)
def add_favorite(payload: FavoriteCreate, db: Session = Depends(get_db)):
    ticker = normalize_symbol(payload.ticker)
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    company = find_or_create_asset(db, ticker, track_reason="favorite_asset")
    if not company:
        raise HTTPException(status_code=404, detail="Tracked asset not found")

    existing = db.execute(
        select(FavoriteCompany).where(FavoriteCompany.company_id == company.id)
    ).scalar_one_or_none()

    if existing:
        if payload.notes is not None and existing.notes != payload.notes:
            existing.notes = payload.notes
            db.commit()
        serialized = _serialize_favorite(
            db,
            existing,
            fetch_alpha_quotes([existing.company.ticker]) if existing.company else None,
        )
        if serialized:
            return serialized
        raise HTTPException(status_code=500, detail="Unable to serialize favorite")

    max_sort = db.scalar(select(func.max(FavoriteCompany.sort_order))) or 0
    fav = FavoriteCompany(
        company_id=company.id,
        notes=payload.notes,
        sort_order=max_sort + 1,
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    serialized = _serialize_favorite(
        db,
        fav,
        fetch_alpha_quotes([fav.company.ticker]) if fav.company else None,
    )
    if serialized:
        return serialized
    raise HTTPException(status_code=500, detail="Unable to serialize favorite")


@router.delete("/{ticker}")
def delete_favorite(ticker: str, db: Session = Depends(get_db)):
    company = _resolve_company(db, ticker)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    fav = db.execute(
        select(FavoriteCompany).where(FavoriteCompany.company_id == company.id)
    ).scalar_one_or_none()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    return {"status": "deleted", "ticker": company.ticker}
