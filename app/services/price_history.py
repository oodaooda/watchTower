from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import AssetPriceDaily, Company

ALPHA_ENDPOINT = "https://www.alphavantage.co/query"
EOD_STALE_AFTER_DAYS = 2


def fetch_alpha_daily_adjusted(symbol: str, api_key: str) -> List[Tuple[date, float]]:
    try:
        res = requests.get(
            ALPHA_ENDPOINT,
            params={
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": symbol,
                "outputsize": "full",
                "apikey": api_key,
            },
            timeout=30,
        )
        res.raise_for_status()
        payload = res.json() or {}
    except Exception as exc:  # pragma: no cover - network variability
        raise HTTPException(status_code=502, detail=f"Alpha Vantage daily data unavailable: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Alpha Vantage daily data unavailable")
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        raise HTTPException(status_code=502, detail="Alpha Vantage daily data unavailable")

    points: List[Tuple[date, float]] = []
    for ts_str, row in series.items():
        if not isinstance(row, dict):
            continue
        try:
            price_date = datetime.strptime(ts_str, "%Y-%m-%d").date()
            close_price = float(row["5. adjusted close"])
            points.append((price_date, close_price))
        except (KeyError, TypeError, ValueError):
            continue
    points.sort(key=lambda item: item[0])
    return points


def load_daily_history(db: Session, company: Company) -> List[AssetPriceDaily]:
    return db.scalars(
        select(AssetPriceDaily)
        .where(AssetPriceDaily.company_id == company.id)
        .order_by(AssetPriceDaily.price_date.asc())
    ).all()


def upsert_daily_history(
    db: Session,
    company: Company,
    points: Iterable[Tuple[date, float]],
    *,
    source: str = "alpha_vantage",
) -> List[AssetPriceDaily]:
    existing = {
        row.price_date: row
        for row in db.scalars(
            select(AssetPriceDaily).where(AssetPriceDaily.company_id == company.id)
        ).all()
    }

    for price_date, close_price in points:
        row = existing.get(price_date)
        if row:
            row.close_price = Decimal(str(close_price))
            row.source = source
        else:
            db.add(
                AssetPriceDaily(
                    company_id=company.id,
                    price_date=price_date,
                    close_price=Decimal(str(close_price)),
                    source=source,
                )
            )

    db.commit()
    return load_daily_history(db, company)


def ensure_daily_history(
    db: Session,
    company: Company,
    *,
    force_refresh: bool = False,
) -> List[AssetPriceDaily]:
    rows = load_daily_history(db, company)
    if not settings.alpha_vantage_api_key:
        return rows

    latest_date = rows[-1].price_date if rows else None
    is_stale = latest_date is None or latest_date < (date.today() - timedelta(days=EOD_STALE_AFTER_DAYS))
    if force_refresh or is_stale:
        points = fetch_alpha_daily_adjusted(company.ticker.upper(), settings.alpha_vantage_api_key)
        rows = upsert_daily_history(db, company, points)
    return rows


def sync_tracked_assets_daily_history(db: Session) -> int:
    if not settings.alpha_vantage_api_key:
        return 0

    assets = db.scalars(
        select(Company)
        .where(Company.is_tracked.is_(True))
        .order_by(Company.ticker.asc())
    ).all()

    synced = 0
    for asset in assets:
        ensure_daily_history(db, asset)
        synced += 1
    return synced
