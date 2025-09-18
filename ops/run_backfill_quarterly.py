"""Backfill quarterly fundamentals into financials_quarterly.

- Pulls SEC companyfacts JSON.
- Extracts quarterly USD values for key items (Revenue, NI, CFO, CapEx, etc.).
- Tries preferred us-gaap tags first.
- Falls back to keyword search if standard tags are missing.
- Upserts into financials_quarterly (idempotent).
"""

import argparse, time
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.core.models import Company, FinancialQuarterly
from app.etl.sec_fetch_companyfacts import (
    fetch_companyfacts,
    extract_quarterly_usd_facts,
    list_available_tags,
)

from app.etl.sec_utils import (
    get_series_with_fallback, FALLBACK_KEYWORDS,
    REV_TAGS, NI_TAGS, CFO_TAGS, CAPEX_TAGS, COGS_TAGS, GP_TAGS, RND_TAGS,
    SGA_TAGS, OPINC_TAGS, INTEXP_TAGS, TAXEXP_TAGS,
    ASSETS_TAGS, LIABC_TAGS, LIABLT_TAGS, EQUITY_TAGS,
    INV_TAGS, AR_TAGS, AP_TAGS, CASH_TAGS, DEBT_TAGS, SHARES_TAGS,
    DEP_TAGS, SBC_TAGS, DIV_TAGS, REP_TAGS,
)


def backfill_company_quarterly(db: Session, company: Company, debug: bool = False) -> int:
    if company.cik is None:
        return 0
    cf = fetch_companyfacts(int(company.cik))
    if not cf:
        return 0

    # 🔹 CHANGED: use unified helper
    maps = {
        "revenue": get_series_with_fallback(cf, REV_TAGS, FALLBACK_KEYWORDS["revenue"], "quarterly"),
        "net_income": get_series_with_fallback(cf, NI_TAGS, FALLBACK_KEYWORDS["net_income"], "quarterly"),
        "cfo": get_series_with_fallback(cf, CFO_TAGS, FALLBACK_KEYWORDS["cfo"], "quarterly"),
        "capex": get_series_with_fallback(cf, CAPEX_TAGS, FALLBACK_KEYWORDS["capex"], "quarterly"),
        "cost_of_revenue": get_series_with_fallback(cf, COGS_TAGS, FALLBACK_KEYWORDS["cost_of_revenue"], "quarterly"),
        "gross_profit": get_series_with_fallback(cf, GP_TAGS, FALLBACK_KEYWORDS["gross_profit"], "quarterly"),
        "research_and_development": get_series_with_fallback(cf, RND_TAGS, FALLBACK_KEYWORDS["research_and_development"], "quarterly"),
        "selling_general_admin": get_series_with_fallback(cf, SGA_TAGS, FALLBACK_KEYWORDS["selling_general_admin"], "quarterly"),
        "operating_income": get_series_with_fallback(cf, OPINC_TAGS, FALLBACK_KEYWORDS["operating_income"], "quarterly"),
        "interest_expense": get_series_with_fallback(cf, INTEXP_TAGS, FALLBACK_KEYWORDS["interest_expense"], "quarterly"),
        "income_tax_expense": get_series_with_fallback(cf, TAXEXP_TAGS, FALLBACK_KEYWORDS["income_tax_expense"], "quarterly"),
        "assets_total": get_series_with_fallback(cf, ASSETS_TAGS, FALLBACK_KEYWORDS["assets_total"], "quarterly"),
        "liabilities_current": get_series_with_fallback(cf, LIABC_TAGS, FALLBACK_KEYWORDS["liabilities_current"], "quarterly"),
        "liabilities_longterm": get_series_with_fallback(cf, LIABLT_TAGS, FALLBACK_KEYWORDS["liabilities_longterm"], "quarterly"),
        "equity_total": get_series_with_fallback(cf, EQUITY_TAGS, FALLBACK_KEYWORDS["equity_total"], "quarterly"),
        "inventories": get_series_with_fallback(cf, INV_TAGS, FALLBACK_KEYWORDS["inventories"], "quarterly"),
        "accounts_receivable": get_series_with_fallback(cf, AR_TAGS, FALLBACK_KEYWORDS["accounts_receivable"], "quarterly"),
        "accounts_payable": get_series_with_fallback(cf, AP_TAGS, FALLBACK_KEYWORDS["accounts_payable"], "quarterly"),
        "cash_and_sti": get_series_with_fallback(cf, CASH_TAGS, FALLBACK_KEYWORDS["cash_and_sti"], "quarterly"),
        "total_debt": get_series_with_fallback(cf, DEBT_TAGS, FALLBACK_KEYWORDS["total_debt"], "quarterly"),
        "shares_outstanding": get_series_with_fallback(cf, SHARES_TAGS, FALLBACK_KEYWORDS["shares_outstanding"], "quarterly"),
        "depreciation_amortization": get_series_with_fallback(cf, DEP_TAGS, FALLBACK_KEYWORDS["depreciation_amortization"], "quarterly"),
        "share_based_comp": get_series_with_fallback(cf, SBC_TAGS, FALLBACK_KEYWORDS["share_based_comp"], "quarterly"),
        "dividends_paid": get_series_with_fallback(cf, DIV_TAGS, FALLBACK_KEYWORDS["dividends_paid"], "quarterly"),
        "share_repurchases": get_series_with_fallback(cf, REP_TAGS, FALLBACK_KEYWORDS["share_repurchases"], "quarterly"),
    }

    keys = set().union(*[m.keys() for m in maps.values()])
    rows_written = 0
    for (fy, fp) in sorted(keys):
        values = {"company_id": company.id, "fiscal_year": fy, "fiscal_period": fp, "source": "sec"}
        for field, m in maps.items():
            values[field] = m.get((fy, fp))

        stmt = pg_insert(FinancialQuarterly).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[FinancialQuarterly.company_id, FinancialQuarterly.fiscal_year, FinancialQuarterly.fiscal_period],
            set_={k: stmt.excluded[k] for k in values if k not in ("company_id","fiscal_year","fiscal_period")},
        )
        db.execute(stmt)
        rows_written += 1

    db.commit()
    return rows_written




# ----------------------------
# CLI
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Backfill quarterly financials")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--ticker", type=str)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        q = select(Company).where(Company.is_tracked == True)
        if args.ticker:
            q = q.where(Company.ticker == args.ticker.upper())
        q = q.order_by(Company.ticker).limit(args.limit)

        companies = db.scalars(q).all()
        total = 0
        for co in companies:
            n = backfill_company_quarterly(db, co, args.debug)
            print(f"[quarterly] {co.ticker}: wrote {n} quarter(s)")
            total += n
            time.sleep(0.5)
        print(f"[quarterly] Done. Total quarters written: {total}")
    finally:
        db.close()

if __name__ == "__main__":
    main()