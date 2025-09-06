# ops/backfill_industries.py
# ------------------------------------------------------------
# Backfill companies.industry_name using identifiers in your DB.
#
# Source of truth for Industry text:
#   - Alpha Vantage "OVERVIEW" endpoint → field "Industry"
# Optional assist (SIC/cik sanity):
#   - SEC company_tickers.json (download once, local or remote)
#
# No CSVs. No "SIC {code}" labels. Only real industry strings.
#
# Usage:
#   # env: DATABASE_URL and ALPHA_VANTAGE_API_KEY in .env
#   PYTHONPATH=. python -m ops.backfill_industries
#
# Options:
#   --force           update all rows (not just NULL industry_name)
#   --only-tracked    limit to is_tracked = TRUE (default: all with ticker)
#   --limit 500       cap rows processed
#   --sleep 12        seconds between AV calls (respect rate limits)
#   --sec-json /app/data/company_tickers.json   (optional)

# TO run Use: PYTHONPATH=. python -m ops.backfill_industries --force --only-tracked --sleep .5

# ------------------------------------------------------------
from __future__ import annotations

import argparse
import os
import time
from typing import Dict, Optional, Tuple

import requests
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.models import Company

# ------------- Alpha Vantage -------------
AV_OVERVIEW_URL = "https://www.alphavantage.co/query?function=OVERVIEW&symbol={sym}&apikey={key}"

def av_overview_industry(ticker: str, api_key: Optional[str]) -> Optional[str]:
    """Fetch Industry string from AV OVERVIEW (returns None if missing)."""
    if not api_key:
        return None
    try:
        r = requests.get(AV_OVERVIEW_URL.format(sym=ticker, key=api_key), timeout=30)
        if r.status_code == 200:
            j = r.json()
            # AV returns {} on not found / throttled; "Note" key when throttled
            ind = j.get("Industry")
            if ind and isinstance(ind, str) and ind.strip():
                return ind.strip()
        return None
    except requests.RequestException:
        return None

# ------------- SEC (optional helper) -------------
def load_sec_company_tickers_json(path: Optional[str]) -> Dict[str, dict]:
    """Load SEC company_tickers.json into a dict keyed by upper TICKER."""
    if not path or not os.path.exists(path):
        return {}
    try:
        j = requests.get(path, timeout=30).json() if path.startswith("http") else __import__("json").load(open(path))
    except Exception:
        return {}
    out: Dict[str, dict] = {}
    # file is usually an object {"0": {...}, "1": {...}, ...}
    for _, row in (j.items() if isinstance(j, dict) else []):
        t = (row.get("ticker") or "").strip().upper()
        if not t:
            continue
        out[t] = row
    return out

# ------------- Main job -------------
def run(force: bool, only_tracked: bool, limit: int, sleep_s: float, sec_json_path: Optional[str]) -> None:
    apikey = settings.alpha_vantage_api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
    sec_map = load_sec_company_tickers_json(sec_json_path) if sec_json_path else {}

    db: Session = SessionLocal()
    try:
        stmt = select(Company).where(Company.ticker.isnot(None))
        if not force:
            stmt = stmt.where(Company.industry_name.is_(None))
        if only_tracked:
            stmt = stmt.where(Company.is_tracked.is_(True))
        stmt = stmt.order_by(Company.ticker.asc()).limit(limit)

        companies = db.scalars(stmt).all()
        if not companies:
            print("[industries] Nothing to do.")
            return

        print(f"[industries] processing {len(companies)} company rows (force={force}, tracked={only_tracked})")

        updated = 0
        throttles = 0
        for co in companies:
            tkr = (co.ticker or "").upper().strip()
            if not tkr:
                continue

            # (Optional) If SEC map present, backfill SIC when missing (no CSV).
            if sec_map and (co.sic is None):
                sec_row = sec_map.get(tkr)
                if sec_row and sec_row.get("sic") is not None:
                    sic_str = str(sec_row["sic"]).strip()
                    if sic_str:
                        db.execute(
                            update(Company)
                            .where(Company.id == co.id)
                            .values(sic=sic_str)
                        )
                        db.commit()

            # Get Industry name from Alpha Vantage OVERVIEW
            industry = av_overview_industry(tkr, apikey)
            if industry:
                db.execute(
                    update(Company)
                    .where(Company.id == co.id)
                    .values(industry_name=industry)
                )
                db.commit()
                updated += 1
                print(f"[industries] {tkr}: industry='{industry}'")
            else:
                print(f"[industries] {tkr}: no industry (AV unavailable or empty)")
                throttles += 1

            # Rate-limit AV calls politely
            time.sleep(sleep_s)

        print(f"[industries] Done. Updated {updated} row(s). Missing/Skipped: {throttles}.")
    finally:
        db.close()

def main():
    p = argparse.ArgumentParser(description="Backfill companies.industry_name from Alpha Vantage OVERVIEW (no CSV).")
    p.add_argument("--force", action="store_true", help="Update all rows (not just NULL industry_name).")
    p.add_argument("--only-tracked", action="store_true", help="Limit to is_tracked = TRUE.")
    p.add_argument("--limit", type=int, default=5000, help="Max companies to process.")
    p.add_argument("--sleep", type=float, default=12.0, help="Seconds between AV calls (respect rate limits).")
    p.add_argument("--sec-json", type=str, default=None,
                   help="Optional path or URL to SEC company_tickers.json to backfill missing SIC.")
    args = p.parse_args()
    run(force=args.force, only_tracked=args.only_tracked, limit=args.limit, sleep_s=args.sleep, sec_json_path=args.sec_json)

if __name__ == "__main__":
    main()
