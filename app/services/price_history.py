from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import time
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from fastapi import HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import AssetPriceDaily, Company, PortfolioPosition

ALPHA_ENDPOINT = "https://www.alphavantage.co/query"
EOD_STALE_AFTER_DAYS = 2
DEFAULT_ALPHA_DAILY_SLEEP_SECONDS = 12.0
ALPHA_RATE_LIMIT_RETRY_SECONDS = 15.0


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
    if payload.get("Note") or payload.get("Information"):
        raise HTTPException(status_code=429, detail=str(payload.get("Note") or payload.get("Information")))
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
    for idx, asset in enumerate(assets):
        try:
            ensure_daily_history(db, asset)
            synced += 1
        except HTTPException as exc:
            if exc.status_code == 429:
                time.sleep(ALPHA_RATE_LIMIT_RETRY_SECONDS)
                try:
                    ensure_daily_history(db, asset, force_refresh=True)
                    synced += 1
                except HTTPException:
                    pass
            else:
                continue
        if idx < len(assets) - 1:
            time.sleep(DEFAULT_ALPHA_DAILY_SLEEP_SECONDS)
    return synced


def portfolio_assets(db: Session) -> List[Company]:
    company_ids = (
        select(distinct(PortfolioPosition.company_id))
        .where(PortfolioPosition.company_id.is_not(None))
    )
    return db.scalars(
        select(Company)
        .where(Company.id.in_(company_ids))
        .order_by(Company.ticker.asc())
    ).all()


def backfill_assets_daily_history(
    db: Session,
    assets: List[Company],
    *,
    force_refresh: bool = True,
    sleep_seconds: float = 12.0,
) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    succeeded_assets = 0
    failed_assets = 0

    for idx, asset in enumerate(assets):
        try:
            rows = ensure_daily_history(db, asset, force_refresh=force_refresh)
            latest_price_date = rows[-1].price_date.isoformat() if rows else None
            items.append(
                {
                    "ticker": asset.ticker,
                    "status": "ok",
                    "history_rows": len(rows),
                    "latest_price_date": latest_price_date,
                    "error": None,
                }
            )
            succeeded_assets += 1
        except HTTPException as exc:
            items.append(
                {
                    "ticker": asset.ticker,
                    "status": "error",
                    "history_rows": 0,
                    "latest_price_date": None,
                    "error": str(exc.detail),
                }
            )
            failed_assets += 1
        except Exception as exc:  # pragma: no cover - network variability
            items.append(
                {
                    "ticker": asset.ticker,
                    "status": "error",
                    "history_rows": 0,
                    "latest_price_date": None,
                    "error": str(exc),
                }
            )
            failed_assets += 1

        if sleep_seconds > 0 and idx < len(assets) - 1:
            time.sleep(sleep_seconds)

    return {
        "total_assets": len(assets),
        "attempted_assets": len(assets),
        "succeeded_assets": succeeded_assets,
        "failed_assets": failed_assets,
        "items": items,
    }


def backfill_portfolio_daily_history(
    db: Session,
    *,
    force_refresh: bool = True,
    sleep_seconds: float = 12.0,
) -> Dict[str, object]:
    assets = portfolio_assets(db)
    return backfill_assets_daily_history(
        db,
        assets,
        force_refresh=force_refresh,
        sleep_seconds=sleep_seconds,
    )


def complete_portfolio_price_dates(db: Session) -> List[date]:
    assets = portfolio_assets(db)
    if not assets:
        return []
    company_ids = [asset.id for asset in assets]
    required_count = len(company_ids)
    rows = db.execute(
        select(AssetPriceDaily.price_date)
        .where(AssetPriceDaily.company_id.in_(company_ids))
        .group_by(AssetPriceDaily.price_date)
        .having(func.count(distinct(AssetPriceDaily.company_id)) == required_count)
        .order_by(AssetPriceDaily.price_date.asc())
    ).all()
    return [row[0] for row in rows]
