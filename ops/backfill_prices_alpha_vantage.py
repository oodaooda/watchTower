# ops/backfill_prices_alpha_vantage.py
"""
Backfill latest close & FY-based P/E (price / FY diluted EPS) into prices_annual.
- Price: Alpha Vantage GLOBAL_QUOTE
- EPS FY: SEC companyfacts (EarningsPerShareDiluted), fallback NI / diluted shares
"""

from __future__ import annotations
import os, time, json, argparse, urllib.request
from typing import Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import Company, FinancialAnnual, PriceAnnual
from app.etl.sec_fetch_companyfacts import fetch_companyfacts

# --- config / rate limiting ---
DEFAULT_SLEEP = 13  # AV free tier ~5/min

def get_av_api_key() -> Optional[str]:
    # Prefer your settings if you have it; fallback to env
    try:
        from app.core.config import settings
        k = getattr(settings, "alpha_vantage_api_key", None) or os.getenv("ALPHAVANTAGE_API_KEY")
        return k
    except Exception:
        return os.getenv("ALPHAVANTAGE_API_KEY")

# --- SEC helpers ---

def _series_map_any_units(cf: Dict, tag: str, prefer_units: List[str] | None = None) -> Dict[int, float]:
    facts = cf.get("facts", {}).get("us-gaap", {})
    if tag not in facts: return {}
    units = facts[tag].get("units", {}) or {}
    chosen = []
    # Prefer requested units
    if prefer_units:
        for u in prefer_units:
            if u in units:
                chosen = [x for x in units[u] if x.get("fy") and x.get("fp") in ("FY", "FYR")]
                break
    # Else pick unit with most annual points
    if not chosen:
        best = []
        for u, arr in units.items():
            pts = [x for x in arr if x.get("fy") and x.get("fp") in ("FY", "FYR")]
            if len(pts) > len(best): best = pts
        chosen = best
    out = {}
    for x in chosen:
        try:
            out[int(x["fy"])] = float(x["val"])
        except Exception:
            pass
    return out

def eps_diluted_fy(cf: Dict) -> Dict[int, float]:
    eps = _series_map_any_units(cf, "EarningsPerShareDiluted", ["USD/shares", "USD / shares"])
    if eps: return eps
    ni  = _series_map_any_units(cf, "NetIncomeLoss", ["USD"])
    dil = _series_map_any_units(cf, "WeightedAverageNumberOfDilutedSharesOutstanding", ["shares"])
    out = {}
    for y in set(ni) & set(dil):
        if dil[y]:
            out[y] = ni[y] / dil[y]
    return out

# --- Alpha Vantage ---

def av_global_quote(symbol: str, api_key: str) -> Optional[float]:
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    q = data.get("Global Quote") or data.get("GlobalQuote")
    if not q: return None
    price = q.get("05. price") or q.get("05. Price")
    try:
        return float(price)
    except Exception:
        return None

# --- main ---

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill close & FY-based P/E into prices_annual")
    parser.add_argument("--ticker", type=str, help="Only this ticker")
    parser.add_argument("--limit", type=int, default=50, help="Max tracked companies")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Sleep between AV calls")
    args = parser.parse_args()

    apikey = get_av_api_key()
    if not apikey:
        raise SystemExit("ALPHAVANTAGE_API_KEY not set in env/.env")

    db: Session = SessionLocal()
    try:
        q = select(Company).where(Company.is_tracked.is_(True))
        if args.ticker:
            q = q.where(Company.ticker == args.ticker.upper())
        q = q.order_by(Company.ticker).limit(args.limit)
        cos = db.scalars(q).all()

        wrote = 0
        for co in cos:
            # latest FY we have fundamentals for
            latest_fy = db.execute(
                select(func.max(FinancialAnnual.fiscal_year)).where(FinancialAnnual.company_id == co.id)
            ).scalar()
            if latest_fy is None:
                print(f"[prices] {co.ticker}: skip (no fundamentals yet)")
                continue

            # EPS FY from SEC
            if not co.cik:
                print(f"[prices] {co.ticker}: skip (no CIK)")
                continue
            cf = fetch_companyfacts(int(co.cik))
            if not cf:
                print(f"[prices] {co.ticker}: skip (no companyfacts)")
                continue
            eps_map = eps_diluted_fy(cf)
            eps = eps_map.get(int(latest_fy))
            if not eps:
                print(f"[prices] {co.ticker}: skip (no EPS for {latest_fy})")
                continue

            # Latest price
            price = av_global_quote(co.ticker, apikey)
            if price is None:
                print(f"[prices] {co.ticker}: skip (no price)")
                continue

            pe = price / eps if eps else None
            ins = pg_insert(PriceAnnual).values(
                company_id=co.id,
                fiscal_year=int(latest_fy),
                close_price=price,
                pe_ttm=pe,
                source="alphavantage",
            )
            ins = pg_insert(PriceAnnual).values(
                company_id=co.id,
                fiscal_year=int(latest_fy),
                close_price=price,
                pe_ttm=pe,
                # source="alphavantage",  # <-- remove if you don't have this column
            )
            stmt = ins.on_conflict_do_update(
                index_elements=[PriceAnnual.company_id, PriceAnnual.fiscal_year],
                set_={
                    "close_price": ins.excluded.close_price,
                    "pe_ttm": ins.excluded.pe_ttm,
                    "source": ins.excluded.source,
                },
            )


            db.execute(stmt)
            db.commit()
            wrote += 1
            print(f"[prices] {co.ticker}: FY {latest_fy} price={price:.4f} eps={eps:.4f} pe={pe:.2f}")

            time.sleep(args.sleep)
        print(f"[prices] Done. wrote {wrote} row(s).")
    finally:
        db.close()

if __name__ == "__main__":
    main()
