from __future__ import annotations

import time
from typing import Dict, Iterable

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import Company, PriceAnnual
from app.services.assets import normalize_symbol

QUOTE_TTL = 30
_QUOTE_CACHE: Dict[str, tuple[float, Dict[str, float | None | str]]] = {}


def to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coalesce(*values):
    for value in values:
        if value is not None:
            return value
    return None


def ratio(a, b):
    if a is None or b in (None, 0):
        return None
    try:
        return float(a) / float(b)
    except ZeroDivisionError:
        return None


def fetch_alpha_quotes(tickers: Iterable[str]) -> Dict[str, Dict[str, float | None | str]]:
    api_key = settings.alpha_vantage_api_key
    if not api_key:
        return {}

    quotes: Dict[str, Dict[str, float | None | str]] = {}
    now = time.time()
    for symbol in sorted({normalize_symbol(ticker) for ticker in tickers if ticker}):
        cached = _QUOTE_CACHE.get(symbol)
        if cached and now - cached[0] < QUOTE_TTL:
            quotes[symbol] = cached[1]
            continue

        params = {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": api_key}
        try:
            response = requests.get("https://www.alphavantage.co/query", params=params, timeout=15)
            response.raise_for_status()
            payload = (response.json() or {}).get("Global Quote") or {}
            price = to_float(payload.get("05. price"))
            prev_close = to_float(payload.get("08. previous close"))
            change_pct = payload.get("10. change percent")
            if isinstance(change_pct, str):
                try:
                    change_percent = float(change_pct.strip().strip("%")) / 100.0
                except ValueError:
                    change_percent = None
            else:
                change_percent = to_float(change_pct if isinstance(change_pct, (int, float)) else None)
            quote = {
                "price": price,
                "previous_close": prev_close,
                "change_percent": change_percent,
                "source": "alpha_vantage",
                "status": "live" if price is not None else "unavailable",
            }
            _QUOTE_CACHE[symbol] = (now, quote)
            quotes[symbol] = quote
        except Exception:
            continue
    return quotes


def resolve_current_quote(
    db: Session,
    asset: Company,
    quote_map: Dict[str, Dict[str, float | None | str]] | None = None,
) -> Dict[str, float | None | str]:
    quote = quote_map.get(normalize_symbol(asset.ticker)) if quote_map else None
    if quote and quote.get("price") is not None:
        return {
            "price": quote.get("price"),
            "previous_close": quote.get("previous_close"),
            "change_percent": quote.get("change_percent"),
            "source": quote.get("source") or "alpha_vantage",
            "status": quote.get("status") or "live",
        }

    annual_price = db.scalars(
        select(PriceAnnual)
        .where(PriceAnnual.company_id == asset.id)
        .order_by(PriceAnnual.fiscal_year.desc())
        .limit(1)
    ).first()
    cached_price = to_float(getattr(annual_price, "close_price", None))
    if cached_price is not None:
        return {
            "price": cached_price,
            "previous_close": cached_price,
            "change_percent": None,
            "source": "prices_annual",
            "status": "cached",
        }

    return {
        "price": None,
        "previous_close": None,
        "change_percent": None,
        "source": None,
        "status": "unavailable",
    }
