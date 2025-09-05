"""Seed `companies` from SEC's official ticker↔CIK list.

What this does
--------------
- Downloads https://www.sec.gov/files/company_tickers.json (official SEC map)
- **UPSERTS** rows into the `companies` table on the unique key **CIK** using
  PostgreSQL's `ON CONFLICT DO UPDATE` (idempotent; safe to re-run).
- Deduplicates input by CIK in case the feed contains multiple entries per CIK
  (e.g., multiple share classes mapping to the same registrant).

Why separate from tracking?
---------------------------
Seeding gives you a complete, canonical universe keyed by **CIK**. A separate
selection step (rule-based or user watchlist) will set `is_tracked=True` for the
subset you want to ingest nightly.

Requirements
------------
- Environment variable `SEC_USER_AGENT` (be descriptive, include contact info)
- Network access to sec.gov

Usage
-----
$ python -m ops.seed_companies

Notes
-----
- The SEC endpoint returns a JSON object with numeric keys; each value has
  `ticker`, `cik_str`, and `title`.
- We intentionally do **not** set `sic`/`industry_name` here (needs a separate
  enrichment step if desired).
- This version uses **PostgreSQL upsert** to avoid `duplicate key value` errors
  on the unique CIK index (e.g., `ix_companies_cik`).
"""
from __future__ import annotations

from typing import Dict, Any, List
import datetime as dt

import requests
from sqlalchemy import literal
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.models import Company

URL = "https://www.sec.gov/files/company_tickers.json"
HEADERS = {"User-Agent": settings.sec_user_agent}


def fetch_sec_ticker_map() -> Dict[str, Any]:
    """Download the SEC ticker↔CIK map and return parsed JSON.

    Returns:
        Dict[str, {"ticker": str, "cik_str": int, "title": str}]
    """
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _normalize_row(row: Dict[str, Any]) -> dict | None:
    """Normalize one SEC entry to our Company insert dict.

    Returns None if required fields are missing.
    """
    try:
        cik = int(row.get("cik_str"))
    except Exception:
        return None
    ticker = (row.get("ticker") or "").upper().strip()
    name = (row.get("title") or "").strip()
    if not (cik and ticker and name):
        return None
    return {
        "cik": cik,
        "ticker": ticker,
        "name": name,
        "status": "active",
        "currency": "USD",
        "is_tracked": False,
        # leave other nullable columns as DB/Python defaults
    }


def _dedupe_by_cik(data: Dict[str, Any]) -> List[dict]:
    """Collapse possible duplicates so we only attempt one row per CIK."""
    seen: set[int] = set()
    rows: List[dict] = []
    for _, r in data.items():
        d = _normalize_row(r)
        if not d:
            continue
        cik = d["cik"]
        if cik in seen:
            continue
        seen.add(cik)
        rows.append(d)
    return rows


def upsert_companies(data: Dict[str, Any]) -> None:
    """Bulk upsert companies by CIK using PostgreSQL ON CONFLICT.

    This avoids duplicate key errors when multiple entries in the same batch
    share a CIK, or when re-running the seed.
    """
    rows = _dedupe_by_cik(data)
    if not rows:
        print("[watchTower] No rows to upsert.")
        return

    db: Session = SessionLocal()
    try:
        # Chunk to keep parameter lists reasonable
        chunk_sz = 500
        total = 0
        for i in range(0, len(rows), chunk_sz):
            chunk = rows[i : i + chunk_sz]
            stmt = pg_insert(Company).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Company.cik],
                set_={
                    "ticker": stmt.excluded.ticker,
                    "name": stmt.excluded.name,
                    "status": stmt.excluded.status,   # ✅ use the insert row’s value
                },
            )
            db.execute(stmt)
            total += len(chunk)
        db.commit()
        print(f"[watchTower] Upserted {total} companies (deduped by CIK).")
    finally:
        db.close()



def main() -> None:
    data = fetch_sec_ticker_map()
    upsert_companies(data)


if __name__ == "__main__":
    main()
