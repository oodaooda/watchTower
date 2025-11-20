from __future__ import annotations

import time
from typing import Dict, Optional, List, Iterable

import time
import requests
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

router = APIRouter(prefix="/favorites", tags=["favorites"])

QUOTE_TTL = 30
_QUOTE_CACHE: Dict[str, tuple[float, Dict[str, float | None]]] = {}


class FavoriteCreate(BaseModel):
    ticker: str
    notes: Optional[str] = None


def _coalesce(*vals):
    for val in vals:
        if val is not None:
            return val
    return None


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(a, b):
    if a is None or b in (None, 0):
        return None
    try:
        return float(a) / float(b)
    except ZeroDivisionError:
        return None


def _fetch_alpha_quotes(tickers: Iterable[str]) -> Dict[str, Dict[str, float | None]]:
    api_key = settings.alpha_vantage_api_key
    if not api_key:
        return {}

    quotes: Dict[str, Dict[str, float | None]] = {}
    now = time.time()
    for sym in sorted({t.upper() for t in tickers if t}):
        cached = _QUOTE_CACHE.get(sym)
        if cached and now - cached[0] < QUOTE_TTL:
            quotes[sym] = cached[1]
            continue

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": sym,
            "apikey": api_key,
        }
        try:
            resp = requests.get("https://www.alphavantage.co/query", params=params, timeout=15)
            resp.raise_for_status()
            payload = (resp.json() or {}).get("Global Quote") or {}
            price = _to_float(payload.get("05. price"))
            prev_close = _to_float(payload.get("08. previous close"))
            change_pct = payload.get("10. change percent")
            if isinstance(change_pct, str):
                try:
                    change_pct_val = float(change_pct.strip().strip("%")) / 100.0
                except ValueError:
                    change_pct_val = None
            else:
                change_pct_val = _to_float(change_pct if isinstance(change_pct, (int, float)) else None)
            quote = {
                "price": price,
                "previous_close": prev_close,
                "change_percent": change_pct_val,
                "source": "alpha_vantage",
            }
            _QUOTE_CACHE[sym] = (now, quote)
            quotes[sym] = quote
        except Exception:
            # leave quote missing; will fall back to cached/annual price
            continue

    return quotes


def _resolve_company(db: Session, ticker: str) -> Company | None:
    if not ticker:
        return None
    return db.execute(
        select(Company).where(Company.ticker == ticker.upper())
    ).scalar_one_or_none()


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

    price = _coalesce(quote and quote.get("price"), _to_float(getattr(price_row, "close_price", None)))
    prev_close = _coalesce(
        quote and quote.get("previous_close"),
        _to_float(getattr(price_row, "close_price", None)),
    )
    if quote and quote.get("change_percent") is not None:
        change_pct = quote.get("change_percent")
    elif price is not None and prev_close not in (None, 0):
        change_pct = _ratio(price - prev_close, prev_close)
    else:
        change_pct = None

    shares = _to_float(getattr(financial, "shares_outstanding", None))
    eps = _coalesce(
        _to_float(getattr(metrics, "ttm_eps", None)),
        _ratio(_to_float(getattr(financial, "net_income", None)), shares),
    )
    pe = _coalesce(
        _to_float(getattr(metrics, "pe_ttm", None)),
        _ratio(price, eps) if price is not None and eps not in (None, 0) else None,
    )
    market_cap = price * shares if (price is not None and shares is not None) else None

    return FavoriteCompanyItem(
        company_id=co.id,
        ticker=co.ticker,
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

    quotes = _fetch_alpha_quotes(fav.company.ticker for fav in favorites if fav.company)

    items: List[FavoriteCompanyItem] = []
    for fav in favorites:
        serialized = _serialize_favorite(db, fav, quotes)
        if serialized:
            items.append(serialized)
    return items


@router.post("", response_model=FavoriteCompanyItem)
def add_favorite(payload: FavoriteCreate, db: Session = Depends(get_db)):
    ticker = (payload.ticker or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")

    company = _resolve_company(db, ticker)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    existing = db.execute(
        select(FavoriteCompany).where(FavoriteCompany.company_id == company.id)
    ).scalar_one_or_none()

    if existing:
        if payload.notes is not None and existing.notes != payload.notes:
            existing.notes = payload.notes
            db.commit()
        serialized = _serialize_favorite(db, existing)
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
    serialized = _serialize_favorite(db, fav)
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
