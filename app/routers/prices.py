# app/routers/prices.py
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import requests
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import Company

router = APIRouter(prefix="/prices", tags=["prices"])

ALPHA_ENDPOINT = "https://www.alphavantage.co/query"

# Simple in-memory cache to avoid hammering Alpha Vantage when the profile
# chart toggles ranges repeatedly.
CacheEntry = Tuple[float, List[Tuple[datetime, float]]]
_CACHE: Dict[Tuple[str, str, Optional[str]], CacheEntry] = {}
NewsCacheEntry = Tuple[float, List[Dict[str, Any]]]
_NEWS_CACHE: Dict[Tuple[str, str], NewsCacheEntry] = {}

INTRADAY_TTL = 60 * 5       # 5 minutes
DAILY_TTL = 60 * 60 * 3     # 3 hours
NEWS_TTL = 60 * 10          # 10 minutes

PriceRange = Query(
    "5y",
    pattern="^(1d|5d|1m|ytd|5y|max)$",
    description="Requested price history window",
)


@router.get("/{identifier}/history")
def price_history(
    identifier: str = Path(..., description="Company id or ticker symbol"),
    range: str = PriceRange,
    db: Session = Depends(get_db),
):
    company = _resolve_company(db, identifier)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    key = settings.alpha_vantage_api_key
    if not key:
        raise HTTPException(status_code=503, detail="Alpha Vantage API key not configured")

    symbol = company.ticker.upper()

    if range == "1d":
        points = _get_intraday(symbol, key, interval="5min")
        sliced = _slice_intraday(points)
    else:
        points = _get_daily(symbol, key)
        sliced = _slice_daily(points, range)

    payload = [
        {"ts": dt.isoformat(), "close": close}
        for dt, close in sliced
    ]

    return {
        "ticker": symbol,
        "range": range,
        "interval": "5min" if range == "1d" else "1d",
        "source": "alpha_vantage",
        "points": payload,
    }


@router.get("/{identifier}/news")
def company_news(
    identifier: str = Path(..., description="Company id or ticker symbol"),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    company = _resolve_company(db, identifier)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    api_key = settings.alpha_vantage_api_key
    if not api_key:
        raise HTTPException(status_code=503, detail="Alpha Vantage API key not configured")

    symbol = company.ticker.upper()
    items = _get_company_news(symbol, api_key, limit)
    return {"ticker": symbol, "items": items}


def _get_intraday(symbol: str, api_key: str, interval: str) -> List[Tuple[datetime, float]]:
    cache_key = ("intraday", symbol, interval)
    cached = _cache_get(cache_key, INTRADAY_TTL)
    if cached is not None:
        return cached

    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": interval,
        "outputsize": "compact",
        "apikey": api_key,
    }
    data = _alpha_request(params)
    series_key = f"Time Series ({interval})"
    series = data.get(series_key)
    if not series:
        raise HTTPException(status_code=502, detail="Alpha Vantage intraday data unavailable")

    points: List[Tuple[datetime, float]] = []
    for ts_str, payload in series.items():
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            close = float(payload["4. close"])
            points.append((dt, close))
        except (ValueError, KeyError, TypeError):
            continue

    points.sort(key=lambda item: item[0])
    _CACHE[cache_key] = (time.time(), points)
    return points


def _get_daily(symbol: str, api_key: str) -> List[Tuple[datetime, float]]:
    cache_key = ("daily", symbol, None)
    cached = _cache_get(cache_key, DAILY_TTL)
    if cached is not None:
        return cached

    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "full",
        "apikey": api_key,
    }
    data = _alpha_request(params)
    series = data.get("Time Series (Daily)")
    if not series:
        raise HTTPException(status_code=502, detail="Alpha Vantage daily data unavailable")

    points: List[Tuple[datetime, float]] = []
    for ts_str, payload in series.items():
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d")
            close = float(payload["5. adjusted close"])
            points.append((dt, close))
        except (ValueError, KeyError, TypeError):
            continue

    points.sort(key=lambda item: item[0])
    _CACHE[cache_key] = (time.time(), points)
    return points


def _get_company_news(symbol: str, api_key: str, limit: int) -> List[Dict[str, Any]]:
    cache_key = (symbol, str(limit))
    cached = _news_cache_get(cache_key, NEWS_TTL)
    if cached is not None:
        return cached

    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": symbol,
        "sort": "LATEST",
        "limit": str(limit),
        "apikey": api_key,
    }
    data = _alpha_request(params)
    feed = data.get("feed", [])
    items: List[Dict[str, Any]] = []
    for entry in feed:
        if not isinstance(entry, dict):
            continue
        tickers = []
        for ts in entry.get("ticker_sentiment", []) or []:
            if isinstance(ts, dict):
                ticker = ts.get("ticker")
                if ticker:
                    tickers.append(ticker)

        published = entry.get("time_published")
        normalized_time = _normalize_news_time(published)

        items.append(
            {
                "id": entry.get("uuid") or entry.get("url"),
                "title": entry.get("title"),
                "summary": entry.get("summary"),
                "url": entry.get("url"),
                "source": entry.get("source"),
                "image_url": entry.get("banner_image"),
                "published_at": normalized_time,
                "sentiment": entry.get("overall_sentiment_label"),
                "tickers": tickers,
            }
        )

    # Prefer articles that explicitly reference the requested symbol
    filtered = [item for item in items if symbol in (item.get("tickers") or [])]
    if not filtered:
        filtered = items

    _NEWS_CACHE[cache_key] = (time.time(), filtered)
    return filtered


def _slice_intraday(points: List[Tuple[datetime, float]]) -> List[Tuple[datetime, float]]:
    if not points:
        return []
    latest_date = points[-1][0].date()
    same_day = [p for p in points if p[0].date() == latest_date]
    return same_day[-400:]  # keep chart manageable


def _slice_daily(points: List[Tuple[datetime, float]], range_name: str) -> List[Tuple[datetime, float]]:
    if not points:
        return []

    latest_dt = points[-1][0]

    if range_name == "5d":
        subset = points[-5:]
    elif range_name == "1m":
        cutoff = latest_dt - timedelta(days=32)
        subset = [p for p in points if p[0] >= cutoff]
    elif range_name == "ytd":
        cutoff = datetime(latest_dt.year, 1, 1)
        subset = [p for p in points if p[0] >= cutoff]
    elif range_name == "5y":
        cutoff = latest_dt - timedelta(days=5 * 366)
        subset = [p for p in points if p[0] >= cutoff]
    elif range_name == "max":
        subset = points
    else:  # default fallback (should not happen)
        subset = points[-250:]

    return _downsample(subset, limit=1200)


def _downsample(points: List[Tuple[datetime, float]], limit: int) -> List[Tuple[datetime, float]]:
    n = len(points)
    if n <= limit:
        return points
    step = max(1, n // limit)
    sliced = points[::step]
    if sliced[-1] != points[-1]:
        sliced.append(points[-1])
    return sliced


def _alpha_request(params: Dict[str, str]):
    attempt = 0
    while True:
        attempt += 1
        try:
            res = requests.get(ALPHA_ENDPOINT, params=params, timeout=30)
            if res.status_code in (429, 503):
                if attempt >= 4:
                    raise HTTPException(status_code=503, detail="Alpha Vantage rate limit hit")
                time.sleep(min(2 ** attempt, 10))
                continue
            res.raise_for_status()
            payload = res.json()
            if "Error Message" in payload:
                raise HTTPException(status_code=404, detail="Ticker not available from Alpha Vantage")
            if "Note" in payload:
                # API limit reached; treat as temporary failure
                raise HTTPException(status_code=503, detail="Alpha Vantage temporarily unavailable")
            return payload
        except requests.RequestException as exc:
            if attempt >= 4:
                raise HTTPException(status_code=503, detail="Alpha Vantage request failed") from exc
            time.sleep(min(2 ** attempt, 10))


def _cache_get(key: Tuple[str, str, Optional[str]], ttl: int) -> Optional[List[Tuple[datetime, float]]]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > ttl:
        _CACHE.pop(key, None)
        return None
    return value


def _news_cache_get(key: Tuple[str, str], ttl: int) -> Optional[List[Dict[str, Any]]]:
    entry = _NEWS_CACHE.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > ttl:
        _NEWS_CACHE.pop(key, None)
        return None
    return value


def _normalize_news_time(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y%m%dT%H%M%SZ"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=None).isoformat() + "Z"
        except ValueError:
            continue
    return value


def _resolve_company(db: Session, identifier: str) -> Optional[Company]:
    ident = (identifier or "").strip()
    if not ident:
        return None

    try:
        company_id = int(ident)
    except ValueError:
        company_id = None

    if company_id is not None:
        company = db.get(Company, company_id)
        if company:
            return company

    upper = ident.upper()
    stmt = select(Company).where(func.upper(Company.ticker) == upper)
    return db.execute(stmt).scalar_one_or_none()
