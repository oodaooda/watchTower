"""Price ingestion helpers (ETL: Extract → Transform → Load)

This module downloads **daily adjusted prices** and rolls them up to **fiscal
years** so we can compute FY close/average prices and (optionally) market cap
and P/E when combined with shares/EPS.

It is written as an **ETL stub**: safe, minimal functions with clear
responsibilities that you can call from a higher-level job.

Key functions:
- `fetch_daily_adjusted(symbol)` → pandas DataFrame with columns [`date`,`adj_close`]
- `assign_fiscal_year(df, fy_end_month)` → adds `fiscal_year` column
- `rollup_to_fy(df, fy_end_month)` → returns one row per fiscal year with
  `close_price` (last trading day) and `avg_price` (mean of adjusted closes)

Notes:
- Uses **adjusted close** for split/dividend continuity.
- The fiscal year label equals the **calendar year in which the FY ends**.
  Example: For FY end month = 3 (March), 2023-04-01 .. 2024-03-31 is **FY 2024**.
- Alpha Vantage is used as the default source, but you can swap providers easily.
"""
from __future__ import annotations

import time
from typing import Optional

import pandas as pd
import requests

from app.core.config import settings

ALPHA_URL = (
    "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={sym}"
    "&apikey={key}&outputsize=full"
)


# -----------------------------
# Extract
# -----------------------------

def fetch_daily_adjusted(symbol: str, api_key: Optional[str] = None, max_retries: int = 4) -> Optional[pd.DataFrame]:
    """Fetch daily adjusted close from Alpha Vantage.

    Returns a DataFrame with columns: `date` (datetime64[ns]), `adj_close` (float).
    On error or missing data, returns `None`.
    """
    key = api_key or settings.alpha_vantage_api_key
    if not key:
        return None

    url = ALPHA_URL.format(sym=symbol, key=key)
    attempt = 0
    while True:
        try:
            r = requests.get(url, timeout=30)
            if r.status_code in (429, 503):
                attempt += 1
                if attempt > max_retries:
                    r.raise_for_status()
                time.sleep(min(2 ** attempt, 10))
                continue
            r.raise_for_status()
            j = r.json()
            ts = j.get("Time Series (Daily)")
            if not ts:
                return None
            df = pd.DataFrame(ts).T.rename_axis("date").reset_index()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["adj_close"] = pd.to_numeric(df["5. adjusted close"], errors="coerce")
            df = df.dropna(subset=["date", "adj_close"]).sort_values("date").reset_index(drop=True)
            return df[["date", "adj_close"]]
        except requests.RequestException:
            attempt += 1
            if attempt > max_retries:
                return None
            time.sleep(min(2 ** attempt, 10))


# -----------------------------
# Transform
# -----------------------------

def _fiscal_year_from_date(ts: pd.Timestamp, fy_end_month: int) -> int:
    """Return the fiscal year label for a given date.

    If the month is **<= fy_end_month**, the fiscal year is the date's year;
    otherwise it's year + 1.
    Example: fy_end_month=3 (Mar). 2023-04-01 → FY 2024; 2024-03-31 → FY 2024.
    """
    return int(ts.year if ts.month <= fy_end_month else ts.year + 1)


def assign_fiscal_year(df: pd.DataFrame, fy_end_month: int = 12) -> pd.DataFrame:
    """Add a `fiscal_year` column based on `fy_end_month`.

    This does **not** modify in place; it returns a new DataFrame.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    out["fiscal_year"] = out["date"].apply(lambda d: _fiscal_year_from_date(pd.Timestamp(d), fy_end_month))
    return out


def rollup_to_fy(df: pd.DataFrame, fy_end_month: int = 12) -> Optional[pd.DataFrame]:
    """Roll daily adjusted closes up to **one row per fiscal year**.

    Returns a DataFrame with columns: `fiscal_year`, `close_price`, `avg_price`,
    where `close_price` is the last trading day's adjusted close in that FY and
    `avg_price` is the arithmetic mean of adjusted closes within that FY.
    """
    if df is None or df.empty:
        return None
    df = assign_fiscal_year(df, fy_end_month)
    grp = (
        df.groupby("fiscal_year", as_index=False)
        .agg(close_price=("adj_close", "last"), avg_price=("adj_close", "mean"))
        .sort_values("fiscal_year")
        .reset_index(drop=True)
    )
    return grp


# -----------------------------
# (Optional) Load
# -----------------------------
# In your ingest job, you would take the DataFrame from `rollup_to_fy()` and
# upsert rows into `prices_annual` keyed by (company_id, fiscal_year). We keep
# persistence outside this module to maintain a clean separation of concerns.


__all__ = [
    "fetch_daily_adjusted",
    "assign_fiscal_year",
    "rollup_to_fy",
]
