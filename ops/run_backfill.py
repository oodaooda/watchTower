"""Backfill annual fundamentals from SEC companyfacts into `financials_annual`.

What this job does
------------------
- Downloads SEC XBRL `companyfacts` for a company (by CIK).
- Extracts annual USD values for key items (Revenue, NI, Cash+STI, Debt).
- NEW: also extracts Operating Cash Flow (OCF), CapEx, and Shares Outstanding.
- For items that have multiple possible tags, we:
    * build a per-tag time series, then
    * pick the **best coverage** (merge-by-preference or sum-of-components).
- Upserts one row per (company_id, fiscal_year), so re-runs are safe/idempotent.

CLI examples
------------
$ python -m ops.run_backfill --ticker AAPL --debug
$ python -m ops.run_backfill --limit 50
"""
from __future__ import annotations

import argparse
import time
from typing import Dict, List, Tuple

from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from app.core.config import settings


from app.core.db import SessionLocal
from app.core.models import Company, FinancialAnnual
from app.etl.sec_fetch_companyfacts import (
    fetch_companyfacts,
    extract_annual_usd_facts,
    list_available_tags,
)

import requests


# ----------------------------
# Tag preference lists (ordered by desirability)
# ----------------------------

# Revenue tags (ASC 606 first, then legacy)
REV_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
    "SalesRevenueGoodsNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]

# Net income
NI_TAGS = ["NetIncomeLoss"]

# Cash + Short-Term Investments
CASH_STI_AGG = ["CashCashEquivalentsAndShortTermInvestments"]
CASH_ONLY = ["CashAndCashEquivalentsAtCarryingValue"]
STI_ONLY = ["ShortTermInvestments", "MarketableSecuritiesCurrent"]

# Total Debt (components + aggregates)
DEBT_CURRENT = [
    "DebtCurrent",
    "LongTermDebtCurrent",
    "CurrentPortionOfLongTermDebt",
    "CurrentPortionOfLongTermDebtAndCapitalLeaseObligations",
    "ShortTermBorrowings",
    "ShortTermDebt",
    "CommercialPaper",
]
DEBT_LT = ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermBorrowings"]
DEBT_AGG = [
    "Debt",
    "LongTermDebtAndFinanceLeaseObligations",
    "LongTermDebtAndCapitalLeaseObligations",
    "LongTermDebt",
]

# CFO (operating cash flow)
OCF_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]

# CapEx
CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "CapitalExpenditures",
    "PaymentsToAcquirePropertyPlantAndEquipmentContinuingOperations",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquirePropertyPlantAndEquipmentExcludingLeasedAssets",
    "PurchaseOfPropertyAndEquipment",
    "PurchasesOfPropertyAndEquipment",
]

# ----------------------------
# Tag preference lists (ordered by desirability)
# ----------------------------
# ... keep existing ...

# NEW: Income statement extras
GROSS_PROFIT_TAGS = ["GrossProfit"]
OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]

# NEW: Balance sheet totals
ASSETS_TAGS = ["Assets"]
EQUITY_TAGS = [
    "StockholdersEquity",  # prefer pure equity when present
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]


# Shares outstanding (end of period)
SHARES_TAGS = ["CommonStockSharesOutstanding"]

# ----------------------------
# Series helpers
# ----------------------------

def series_to_map(series: List[dict]) -> Dict[int, float]:
    """Convert SEC fact series -> {fiscal_year: value} (ints & floats only)."""
    return {
        int(x["fy"]): float(x["val"])
        for x in series
        if x.get("fy") is not None and x.get("val") is not None
    }


def add_series(a_map: Dict[int, float], b_map: Dict[int, float]) -> Dict[int, float]:
    """Elementwise add two FY maps (missing -> 0)."""
    years = set(a_map) | set(b_map)
    return {y: (a_map.get(y, 0.0) or 0.0) + (b_map.get(y, 0.0) or 0.0) for y in years}


def build_tag_maps(cf: Dict, tags: List[str]) -> Dict[str, Dict[int, float]]:
    """Return {tag: {fy: val}} for each candidate tag (no side effects)."""
    out: Dict[str, Dict[int, float]] = {}
    for t in tags:
        out[t] = series_to_map(extract_annual_usd_facts(cf, t))
    return out


def merge_by_preference(tag_maps: Dict[str, Dict[int, float]], pref: List[str]) -> Tuple[str, Dict[int, float]]:
    """For each fiscal year, take the first tag (by pref order) that has a value.

    Returns:
      label: compact string like "TagA(7)+TagB(5)" describing usage counts
      merged_map: {fy: val} merged across tags
    """
    years = set()
    for m in tag_maps.values():
        years |= set(m.keys())

    merged: Dict[int, float] = {}
    used: Dict[str, int] = {t: 0 for t in pref}

    for y in sorted(years):
        for t in pref:
            v = tag_maps.get(t, {}).get(y)
            if v is not None:
                merged[y] = v
                used[t] += 1
                break

    parts = [f"{t}({used[t]})" for t in pref if used.get(t)]
    label = "+".join(parts) if parts else "+".join(pref[:1])
    return label, merged

# ----------------------------
# Main per-company backfill
# ----------------------------

def backfill_company(db: Session, company: Company, debug: bool = False) -> int:
    """Fetch companyfacts and upsert annual rows. Returns years written."""
    if company.cik is None:
        if debug:
            print(f"[watchTower] {company.ticker}: no CIK on record; skipping")
        return 0

    # 1) Fetch companyfacts
    cf = fetch_companyfacts(int(company.cik))
    if not cf:
        if debug:
            print(f"[watchTower] {company.ticker}: empty companyfacts (404 or fetch issue)")
        return 0

    if debug:
        tags = list_available_tags(cf)
        print(f"[watchTower] {company.ticker}: available us-gaap tags (sample): {tags[:20]} ... total={len(tags)}")

    # 2) Revenue & Net Income: merge-by-preference across tags
    rev_maps = build_tag_maps(cf, REV_TAGS)
    rev_label, rev_map = merge_by_preference(rev_maps, REV_TAGS)
    
    ni_maps = build_tag_maps(cf, NI_TAGS)
    ni_label, ni_map = merge_by_preference(ni_maps, NI_TAGS)

    #Expanding Financial Tabs...
    gp_maps = build_tag_maps(cf, GROSS_PROFIT_TAGS)
    gp_label , gp_map = merge_by_preference(gp_maps, GROSS_PROFIT_TAGS)

    op_maps = build_tag_maps(cf, OPERATING_INCOME_TAGS)
    op_label, op_map = merge_by_preference(op_maps, OPERATING_INCOME_TAGS)

    assets_maps = build_tag_maps(cf, ASSETS_TAGS)
    assets_maps, assets_maps = merge_by_preference(assets_maps,ASSETS_TAGS)

    equity_maps = build_tag_maps(cf, EQUITY_TAGS)
    equity_label, equity_maps = merge_by_preference(equity_maps, EQUITY_TAGS)

    # 3) Cash+STI: choose longer of aggregate vs sum(components)
    cash_sti_label, cash_sti_map = merge_by_preference(build_tag_maps(cf, CASH_STI_AGG), CASH_STI_AGG)
    cash_only_label, cash_only_map = merge_by_preference(build_tag_maps(cf, CASH_ONLY), CASH_ONLY)
    sti_only_label, sti_only_map = merge_by_preference(build_tag_maps(cf, STI_ONLY), STI_ONLY)
    comp_sum_map = add_series(cash_only_map, sti_only_map)
    if len(comp_sum_map) > len(cash_sti_map):
        cash_sti_label = f"{cash_only_label}+{sti_only_label} (summed)"
        cash_sti_map = comp_sum_map

    # 4) Debt: choose longer of aggregate vs current+long-term
    debt_label, debt_map = merge_by_preference(build_tag_maps(cf, DEBT_AGG), DEBT_AGG)
    cur_label, cur_map = merge_by_preference(build_tag_maps(cf, DEBT_CURRENT), DEBT_CURRENT)
    lt_label, lt_map = merge_by_preference(build_tag_maps(cf, DEBT_LT), DEBT_LT)
    debt_comp_map = add_series(cur_map, lt_map)
    if len(debt_comp_map) > len(debt_map):
        debt_label = f"{cur_label}+{lt_label} (summed)"
        debt_map = debt_comp_map

    # 5) OCF, CapEx, Shares (simple merge-by-preference)
    ocf_maps = build_tag_maps(cf, OCF_TAGS)
    ocf_label, ocf_map = merge_by_preference(ocf_maps, OCF_TAGS)

    capex_maps = build_tag_maps(cf, CAPEX_TAGS)
    capex_label, capex_map = merge_by_preference(capex_maps, CAPEX_TAGS)


    shares_maps = build_tag_maps(cf, SHARES_TAGS)
    shares_label, shares_map = merge_by_preference(shares_maps, SHARES_TAGS)

    if debug:
        print(
            f"[watchTower] {company.ticker}: chosen -> "
            f"revenue=[{rev_label}] {len(rev_map)}y, "
            f"ni=[{ni_label}] {len(ni_map)}y, "
            f"cash+sti=[{cash_sti_label}] {len(cash_sti_map)}y, "
            f"debt=[{debt_label}] {len(debt_map)}y, "
            f"ocf=[{ocf_label}] {len(ocf_map)}y, "
            f"capex=[{capex_label}] {len(capex_map)}y, "
            f"shares=[{shares_label}] {len(shares_map)}y"
            f"gp=[{gp_label}] {len(gp_map)}y,"
            f"op=[{op_label}] {len(op_map)}y,"
            f" assets=[{assets_maps}] {len(assets_maps)}y, "
            f" equity=[{equity_label}] {len(equity_maps)}y, "

        )

    # 6) Union of all years we have for any series
    years = sorted(
        set(rev_map)
        | set(ni_map)
        | set(cash_sti_map)
        | set(debt_map)
        | set(ocf_map)
        | set(capex_map)
        | set(shares_map)
        | set(gp_map)
        | set(op_map)
        | set(assets_maps)
        | set(equity_maps)
        )
    if debug:
        print(f"[watchTower] {company.ticker}: candidate fiscal years: {years}")
    if not years:
        return 0

    # 7) Upsert each year into financials_annual
    rows_written = 0
    for y in years:
        values = {
            "company_id": company.id,
            "fiscal_year": int(y),
            "fiscal_period": "FY",
            "revenue": rev_map.get(y),
            "net_income": ni_map.get(y),
            "cash_and_sti": cash_sti_map.get(y),
            "total_debt": debt_map.get(y),
            "cfo": ocf_map.get(y),                 # <-- was operating_cash_flow
            "capex": capex_map.get(y),             # <-- was capital_expenditures
            "shares_outstanding": shares_map.get(y),
            "source": "sec",
            "gross_profit": gp_map.get(y),
            "operating_income": op_map.get(y),
            "assets_total": assets_maps.get(y),
            "equity_total": equity_maps.get(y),
                    }

        ins = pg_insert(FinancialAnnual).values(**values)
        stmt = pg_insert(FinancialAnnual).values(**values)
        stmt = stmt.on_conflict_do_update( 
            index_elements=[FinancialAnnual.company_id, FinancialAnnual.fiscal_year],
            set_={
                "revenue": ins.excluded.revenue,
                "net_income": ins.excluded.net_income,
                "cash_and_sti": ins.excluded.cash_and_sti,
                "total_debt": ins.excluded.total_debt,
                "cfo": ins.excluded.cfo,
                "capex": ins.excluded.capex,
                "shares_outstanding": ins.excluded.shares_outstanding,
                "source": ins.excluded.source,
                "gross_profit": ins.excluded.gross_profit,
                "operating_income": ins.excluded.operating_income,
                "assets_total": ins.excluded.assets_total,
                "equity_total": ins.excluded.equity_total,
            },
        )
        db.execute(stmt)
        rows_written += 1

    db.commit()
    return rows_written

# Update company description:

ALPHA_OVERVIEW_URL = "https://www.alphavantage.co/query?function=OVERVIEW&symbol={sym}&apikey={key}"

def fetch_company_overview(symbol: str) -> dict | None:
    if not settings.alpha_vantage_api_key:
        return None

    # Fix: Alpha Vantage uses "." instead of "-" for class shares
    symbol = symbol.replace("-", ".")

    url = ALPHA_OVERVIEW_URL.format(sym=symbol, key=settings.alpha_vantage_api_key)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()

        # If no Description is returned, log and return None
        if not data or "Description" not in data:
            print(f"[overview] No description found for {symbol}")
            return None

        return data
    except Exception as e:
        print(f"[overview] Error fetching {symbol}: {e}")
        return None


def backfill_descriptions(db: Session):
    cos = db.query(Company).filter(
        Company.is_tracked == True,
        or_(Company.description.is_(None), Company.description == "")
    ).all()
    print(f"[overview] Found {len(cos)} companies missing descriptions")

    for co in cos:
        overview = fetch_company_overview(co.ticker)
        if overview and "Description" in overview:
            desc = overview["Description"].strip()
            if desc:
                # 🔹 Use raw SQL update instead of ORM state
                db.execute(
                    Company.__table__.update()
                    .where(Company.id == co.id)
                    .values(description=desc)
                )
                db.commit()  # commit after each update so it persists immediately

                print(f"[overview] Saved {co.ticker}: {desc[:40]}...")
            else:
                print(f"[overview] {co.ticker}: Description empty from Alpha Vantage")
        else:
            print(f"[overview] {co.ticker}: No Description field in response")

        # respect free tier limit (1 request every 12-15s)
        time.sleep(15)


    db.execute(
    Company.__table__.update()
    .where(Company.id == co.id)
    .values(description=desc)
    )

    db.commit()


# ----------------------------
# CLI
# ----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill SEC fundamentals into financials_annual")
    parser.add_argument("--limit", type=int, default=10000, help="Max companies to process")
    parser.add_argument("--ticker", type=str, default=None, help="Only this ticker (exact)")
    parser.add_argument("--company-id", type=int, default=None, help="Only this company_id")
    parser.add_argument("--debug", action="store_true", help="Print tag choices and years")
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
            n = backfill_company(db, co, debug=args.debug)
            print(f"[watchTower] {co.ticker}: wrote {n} year(s)")
            time.sleep(0.5)  # polite to SEC
            total += n
        print(f"[watchTower] Done. Total years written: {total}")

        # 🔹 NEW: backfill descriptions
        backfill_descriptions(db)
        print(f"[overview] Company descriptions updated")

    finally:
        db.close()





if __name__ == "__main__":
    main()
