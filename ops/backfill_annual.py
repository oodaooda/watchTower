"""Backfill annual fundamentals into financials_annual."""

import argparse, time, requests
from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.core.models import Company, FinancialAnnual
from app.core.config import settings
from app.etl.sec_fetch_companyfacts import fetch_companyfacts, list_available_tags
from app.etl.sec_utils import (
    REV_TAGS, NI_TAGS, CASH_STI_AGG, CASH_ONLY, STI_ONLY,
    DEBT_AGG, DEBT_CURRENT, DEBT_LT,
    OCF_TAGS, CAPEX_TAGS, DEP_AMORT_TAGS, SBC_TAGS, DIVIDENDS_TAGS, REPURCHASE_TAGS,
    COGS_TAGS, GROSS_PROFIT_TAGS, RND_TAGS, SGA_TAGS, OPERATING_INCOME_TAGS,
    INT_EXP_TAGS, TAX_EXP_TAGS,
    ASSETS_TAGS, EQUITY_TAGS, LIAB_CURRENT_TAGS, LIAB_LT_TAGS, INVENTORIES_TAGS, AR_TAGS, AP_TAGS,
    SHARES_TAGS,
    build_tag_maps, merge_by_preference, add_series
)

def backfill_company(db: Session, company: Company, debug: bool = False) -> int:
    if company.cik is None:
        return 0
    cf = fetch_companyfacts(int(company.cik))
    if not cf:
        return 0

    # Example: revenue
    _, rev_map = merge_by_preference(build_tag_maps(cf, REV_TAGS), REV_TAGS)
    _, ni_map = merge_by_preference(build_tag_maps(cf, NI_TAGS), NI_TAGS)

    # (similar merges for all tags…)
    # [code omitted for brevity — keep your original full merge logic here]

    years = sorted(set(rev_map) | set(ni_map))
    if not years:
        return 0

    rows_written = 0
    for y in years:
        values = {
            "company_id": company.id,
            "fiscal_year": int(y),
            "fiscal_period": "FY",
            "source": "sec",
            "revenue": rev_map.get(y),
            "net_income": ni_map.get(y),
            # etc — full mapping
        }
        stmt = pg_insert(FinancialAnnual).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[FinancialAnnual.company_id, FinancialAnnual.fiscal_year],
            set_={k: stmt.excluded[k] for k in values.keys() if k not in ("company_id", "fiscal_year")},
        )
        db.execute(stmt)
        rows_written += 1

    db.commit()
    return rows_written

def main():
    parser = argparse.ArgumentParser(description="Backfill annual financials")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--ticker", type=str)
    parser.add_argument("--company-id", type=int)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        q = select(Company).where(Company.is_tracked == True)
        if args.ticker:
            q = q.where(Company.ticker == args.ticker.upper())
        if args.company_id:
            q = q.where(Company.id == args.company_id)
        q = q.order_by(Company.ticker).limit(args.limit)

        companies = db.scalars(q).all()
        total = 0
        for co in companies:
            n = backfill_company(db, co, args.debug)
            print(f"[annual] {co.ticker}: wrote {n} year(s)")
            time.sleep(0.5)
            total += n
        print(f"[annual] Done. Total years written: {total}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
