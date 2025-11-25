"""Backfill multi-year FY close prices using Alpha Vantage daily adjusted series."""
from __future__ import annotations
import argparse
import time

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.models import Company, PriceAnnual
from app.etl.alpha_fetch_prices import fetch_daily_adjusted, rollup_to_fy

DEFAULT_YEARS = 20
DEFAULT_SLEEP = 0.9


def main():
    parser = argparse.ArgumentParser(description="Backfill FY close prices from Alpha Vantage daily data")
    parser.add_argument("--ticker", nargs="*", help="Specific tickers to process")
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP)
    args = parser.parse_args()

    if not settings.alpha_vantage_api_key:
        raise SystemExit("ALPHA_VANTAGE_API_KEY not configured")

    db: Session = SessionLocal()
    try:
        q = select(Company).where(Company.is_tracked.is_(True))
        if args.ticker:
            q = q.where(Company.ticker.in_([t.upper() for t in args.ticker]))
        companies = db.scalars(q).all()
        for co in companies:
            df = fetch_daily_adjusted(co.ticker)
            if df is None or df.empty:
                continue
            fy_end = co.fiscal_year_end_month or 12
            roll = rollup_to_fy(df, fy_end_month=fy_end)
            if roll is None or roll.empty:
                continue
            tail = roll.tail(args.years)
            for _, row in tail.iterrows():
                fy = int(row["fiscal_year"])
                close_price = float(row["close_price"])
                values = {
                    "company_id": co.id,
                    "fiscal_year": fy,
                    "close_price": close_price,
                    "source": "alpha_timeseries",
                }
                stmt = pg_insert(PriceAnnual).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[PriceAnnual.company_id, PriceAnnual.fiscal_year],
                    set_={"close_price": stmt.excluded.close_price, "source": stmt.excluded.source},
                )
                db.execute(stmt)
            db.commit()
            time.sleep(args.sleep)
    finally:
        db.close()

if __name__ == "__main__":
    main()
