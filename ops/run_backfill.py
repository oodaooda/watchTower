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
from app.etl.external_financials import fetch_yahoo_annual_variants
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

# Revenue
REV_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
    "SalesRevenueGoodsNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]

# Net Income
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

# Operating Cash Flow
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

# 🔹 Income Statement Extras
COGS_TAGS = ["CostOfRevenue", "CostOfGoodsAndServicesSold"]
GROSS_PROFIT_TAGS = ["GrossProfit"]
RND_TAGS = ["ResearchAndDevelopmentExpense"]
SGA_TAGS = [
    "SellingGeneralAndAdministrativeExpense",
    "SellingAndMarketingExpense",
    "GeneralAndAdministrativeExpense",
]
SALES_MARKETING_TAGS = [
    "SellingAndMarketingExpense",
    "SalesAndMarketingExpense",
]
GNA_TAGS = [
    "GeneralAndAdministrativeExpense",
    "GeneralAndAdministrativeExpenseOperating",
]
OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]
INT_EXP_TAGS = ["InterestExpense", "InterestExpenseDebt"]
OTHER_INCOME_TAGS = [
    "OtherNonoperatingIncomeExpense",
    "NonoperatingIncomeExpense",
    "OtherIncomeExpense",
    "OtherNonoperatingIncomeExpenseNet",
]
TAX_EXP_TAGS = ["IncomeTaxExpenseBenefit", "IncomeTaxExpenseBenefitContinuingOperations"]

# 🔹 Cash Flow Extras
DEP_AMORT_TAGS = ["DepreciationAndAmortization"]
SBC_TAGS = ["ShareBasedCompensation"]
DIVIDENDS_TAGS = ["PaymentsOfDividends"]
REPURCHASE_TAGS = ["PaymentsForRepurchaseOfCommonStock"]

# 🔹 Balance Sheet Extras
ASSETS_TAGS = ["Assets"]
LIAB_CURRENT_TAGS = ["LiabilitiesCurrent"]
LIAB_LT_TAGS = ["LongTermLiabilitiesNoncurrent"]
EQUITY_TAGS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
INVENTORIES_TAGS = ["InventoryNet"]
AR_TAGS = ["AccountsReceivableNetCurrent"]
AP_TAGS = ["AccountsPayableCurrent"]

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


def _upsert_annual_rows(db: Session, company: Company, rows: List[Dict]) -> int:
    """Upsert a list of annual rows (SEC or external)."""
    rows_written = 0
    for row in rows:
        fy = row.get("fiscal_year")
        if fy is None:
            continue
        values = {
            "company_id": company.id,
            "fiscal_year": int(fy),
            "fiscal_period": row.get("fiscal_period") or "FY",
            "source": row.get("source") or "external",

            # Income Statement
            "revenue": row.get("revenue"),
            "cost_of_revenue": row.get("cost_of_revenue"),
            "gross_profit": row.get("gross_profit"),
            "research_and_development": row.get("research_and_development"),
            "selling_general_admin": row.get("selling_general_admin"),
            "sales_and_marketing": row.get("sales_and_marketing"),
            "general_and_administrative": row.get("general_and_administrative"),
            "operating_income": row.get("operating_income"),
            "interest_expense": row.get("interest_expense"),
            "other_income_expense": row.get("other_income_expense"),
            "income_tax_expense": row.get("income_tax_expense"),
            "net_income": row.get("net_income"),

            # Balance Sheet
            "assets_total": row.get("assets_total"),
            "liabilities_current": row.get("liabilities_current"),
            "liabilities_longterm": row.get("liabilities_longterm"),
            "equity_total": row.get("equity_total"),
            "inventories": row.get("inventories"),
            "accounts_receivable": row.get("accounts_receivable"),
            "accounts_payable": row.get("accounts_payable"),
            "cash_and_sti": row.get("cash_and_sti"),
            "total_debt": row.get("total_debt"),
            "shares_outstanding": row.get("shares_outstanding"),

            # Cash Flow
            "cfo": row.get("cfo"),
            "capex": row.get("capex"),
            "depreciation_amortization": row.get("depreciation_amortization"),
            "share_based_comp": row.get("share_based_comp"),
            "dividends_paid": row.get("dividends_paid"),
            "share_repurchases": row.get("share_repurchases"),
        }

        stmt = pg_insert(FinancialAnnual).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[FinancialAnnual.company_id, FinancialAnnual.fiscal_year],
            set_={
                "revenue": stmt.excluded.revenue,
                "net_income": stmt.excluded.net_income,
                "cash_and_sti": stmt.excluded.cash_and_sti,
                "total_debt": stmt.excluded.total_debt,
                "cfo": stmt.excluded.cfo,
                "capex": stmt.excluded.capex,
                "shares_outstanding": stmt.excluded.shares_outstanding,
                "gross_profit": stmt.excluded.gross_profit,
                "operating_income": stmt.excluded.operating_income,
                "assets_total": stmt.excluded.assets_total,
                "equity_total": stmt.excluded.equity_total,
                "cost_of_revenue": stmt.excluded.cost_of_revenue,
                "research_and_development": stmt.excluded.research_and_development,
                "selling_general_admin": stmt.excluded.selling_general_admin,
                "sales_and_marketing": stmt.excluded.sales_and_marketing,
                "general_and_administrative": stmt.excluded.general_and_administrative,
                "interest_expense": stmt.excluded.interest_expense,
                "other_income_expense": stmt.excluded.other_income_expense,
                "income_tax_expense": stmt.excluded.income_tax_expense,
                "liabilities_current": stmt.excluded.liabilities_current,
                "liabilities_longterm": stmt.excluded.liabilities_longterm,
                "inventories": stmt.excluded.inventories,
                "accounts_receivable": stmt.excluded.accounts_receivable,
                "accounts_payable": stmt.excluded.accounts_payable,
                "depreciation_amortization": stmt.excluded.depreciation_amortization,
                "share_based_comp": stmt.excluded.share_based_comp,
                "dividends_paid": stmt.excluded.dividends_paid,
                "share_repurchases": stmt.excluded.share_repurchases,
                "source": stmt.excluded.source,
            },
        )
        db.execute(stmt)
        rows_written += 1

    db.commit()
    return rows_written

# ----------------------------
# Main per-company backfill
# ----------------------------

def backfill_company(db: Session, company: Company, debug: bool = False) -> int:
    """Fetch companyfacts and upsert annual rows. Returns years written."""

    # --- Skip if no CIK (some OTC tickers, foreign ADRs, etc.)
    if company.cik is None:
        if debug:
            print(f"[watchTower] {company.ticker}: no CIK on record; skipping")
        return 0

    # 1) Fetch companyfacts from SEC
    cf = fetch_companyfacts(int(company.cik))
    if not cf:
        if debug:
            print(f"[watchTower] {company.ticker}: empty companyfacts (404 or fetch issue); trying external fallback")
        ext_rows = fetch_yahoo_annual_variants(company.ticker, company.exchange)
        if ext_rows:
            return _upsert_annual_rows(db, company, ext_rows)
        return 0

    if debug:
        tags = list_available_tags(cf)
        print(f"[watchTower] {company.ticker}: available us-gaap tags (sample): {tags[:20]} ... total={len(tags)}")

    # 2) Core income statement
    rev_label, rev_map = merge_by_preference(build_tag_maps(cf, REV_TAGS), REV_TAGS)
    ni_label, ni_map = merge_by_preference(build_tag_maps(cf, NI_TAGS), NI_TAGS)

    # 3) Income statement extras
    gp_label, gp_map = merge_by_preference(build_tag_maps(cf, GROSS_PROFIT_TAGS), GROSS_PROFIT_TAGS)
    op_label, op_map = merge_by_preference(build_tag_maps(cf, OPERATING_INCOME_TAGS), OPERATING_INCOME_TAGS)
    cogs_label, cogs_map = merge_by_preference(build_tag_maps(cf, COGS_TAGS), COGS_TAGS)
    rnd_label, rnd_map = merge_by_preference(build_tag_maps(cf, RND_TAGS), RND_TAGS)
    sga_label, sga_map = merge_by_preference(build_tag_maps(cf, SGA_TAGS), SGA_TAGS)
    sales_marketing_label, sales_marketing_map = merge_by_preference(
        build_tag_maps(cf, SALES_MARKETING_TAGS), SALES_MARKETING_TAGS
    )
    gna_label, gna_map = merge_by_preference(build_tag_maps(cf, GNA_TAGS), GNA_TAGS)
    int_label, int_map = merge_by_preference(build_tag_maps(cf, INT_EXP_TAGS), INT_EXP_TAGS)
    other_label, other_map = merge_by_preference(build_tag_maps(cf, OTHER_INCOME_TAGS), OTHER_INCOME_TAGS)
    tax_label, tax_map = merge_by_preference(build_tag_maps(cf, TAX_EXP_TAGS), TAX_EXP_TAGS)

    # 4) Balance sheet
    assets_label, assets_map = merge_by_preference(build_tag_maps(cf, ASSETS_TAGS), ASSETS_TAGS)
    equity_label, equity_map = merge_by_preference(build_tag_maps(cf, EQUITY_TAGS), EQUITY_TAGS)
    liab_cur_label, liab_cur_map = merge_by_preference(build_tag_maps(cf, LIAB_CURRENT_TAGS), LIAB_CURRENT_TAGS)
    liab_lt_label, liab_lt_map = merge_by_preference(build_tag_maps(cf, LIAB_LT_TAGS), LIAB_LT_TAGS)
    inv_label, inv_map = merge_by_preference(build_tag_maps(cf, INVENTORIES_TAGS), INVENTORIES_TAGS)
    ar_label, ar_map = merge_by_preference(build_tag_maps(cf, AR_TAGS), AR_TAGS)
    ap_label, ap_map = merge_by_preference(build_tag_maps(cf, AP_TAGS), AP_TAGS)

    # 5) Cash + STI (choose aggregate vs sum-of-components)
    cash_sti_label, cash_sti_map = merge_by_preference(build_tag_maps(cf, CASH_STI_AGG), CASH_STI_AGG)
    cash_only_label, cash_only_map = merge_by_preference(build_tag_maps(cf, CASH_ONLY), CASH_ONLY)
    sti_only_label, sti_only_map = merge_by_preference(build_tag_maps(cf, STI_ONLY), STI_ONLY)
    comp_sum_map = add_series(cash_only_map, sti_only_map)
    if len(comp_sum_map) > len(cash_sti_map):
        cash_sti_label = f"{cash_only_label}+{sti_only_label} (summed)"
        cash_sti_map = comp_sum_map

    # 6) Debt (choose aggregate vs current+long-term)
    debt_label, debt_map = merge_by_preference(build_tag_maps(cf, DEBT_AGG), DEBT_AGG)
    cur_label, cur_map = merge_by_preference(build_tag_maps(cf, DEBT_CURRENT), DEBT_CURRENT)
    lt_label, lt_map = merge_by_preference(build_tag_maps(cf, DEBT_LT), DEBT_LT)
    debt_comp_map = add_series(cur_map, lt_map)
    if len(debt_comp_map) > len(debt_map):
        debt_label = f"{cur_label}+{lt_label} (summed)"
        debt_map = debt_comp_map

    # 7) Cash flow extras
    ocf_label, ocf_map = merge_by_preference(build_tag_maps(cf, OCF_TAGS), OCF_TAGS)
    capex_label, capex_map = merge_by_preference(build_tag_maps(cf, CAPEX_TAGS), CAPEX_TAGS)
    dep_label, dep_map = merge_by_preference(build_tag_maps(cf, DEP_AMORT_TAGS), DEP_AMORT_TAGS)
    sbc_label, sbc_map = merge_by_preference(build_tag_maps(cf, SBC_TAGS), SBC_TAGS)
    div_label, div_map = merge_by_preference(build_tag_maps(cf, DIVIDENDS_TAGS), DIVIDENDS_TAGS)
    rep_label, rep_map = merge_by_preference(build_tag_maps(cf, REPURCHASE_TAGS), REPURCHASE_TAGS)

    # 8) Shares
    shares_label, shares_map = merge_by_preference(build_tag_maps(cf, SHARES_TAGS), SHARES_TAGS)

    # Debug print summary
    if debug:
        print(
            f"[watchTower] {company.ticker}: chosen -> "
            f"revenue=[{rev_label}] {len(rev_map)}y, "
            f"ni=[{ni_label}] {len(ni_map)}y, "
            f"cogs=[{cogs_label}] {len(cogs_map)}y, "
            f"rnd=[{rnd_label}] {len(rnd_map)}y, "
            f"sga=[{sga_label}] {len(sga_map)}y, "
            f"s&m=[{sales_marketing_label}] {len(sales_marketing_map)}y, "
            f"g&a=[{gna_label}] {len(gna_map)}y, "
            f"int=[{int_label}] {len(int_map)}y, "
            f"other=[{other_label}] {len(other_map)}y, "
            f"tax=[{tax_label}] {len(tax_map)}y, "
            f"assets=[{assets_label}] {len(assets_map)}y, "
            f"equity=[{equity_label}] {len(equity_map)}y, "
            f"liab_cur=[{liab_cur_label}] {len(liab_cur_map)}y, "
            f"liab_lt=[{liab_lt_label}] {len(liab_lt_map)}y, "
            f"inv=[{inv_label}] {len(inv_map)}y, "
            f"ar=[{ar_label}] {len(ar_map)}y, "
            f"ap=[{ap_label}] {len(ap_map)}y, "
            f"ocf=[{ocf_label}] {len(ocf_map)}y, "
            f"capex=[{capex_label}] {len(capex_map)}y, "
            f"dep=[{dep_label}] {len(dep_map)}y, "
            f"sbc=[{sbc_label}] {len(sbc_map)}y, "
            f"div=[{div_label}] {len(div_map)}y, "
            f"rep=[{rep_label}] {len(rep_map)}y, "
            f"shares=[{shares_label}] {len(shares_map)}y"
        )

    # 9) Union of all years
    years = sorted(
        set(rev_map) | set(ni_map) | set(cogs_map) | set(rnd_map) | set(sga_map) |
        set(sales_marketing_map) | set(gna_map) | set(int_map) | set(other_map) |
        set(tax_map) | set(gp_map) | set(op_map) |
        set(assets_map) | set(equity_map) | set(liab_cur_map) | set(liab_lt_map) |
        set(inv_map) | set(ar_map) | set(ap_map) |
        set(cash_sti_map) | set(debt_map) |
        set(ocf_map) | set(capex_map) | set(dep_map) | set(sbc_map) | set(div_map) | set(rep_map) |
        set(shares_map)
    )
    if not years:
        # Try external fallback if SEC yielded no series
        ext_rows = fetch_yahoo_annual_variants(company.ticker, company.exchange)
        if ext_rows:
            if debug:
                print(f"[watchTower] {company.ticker}: SEC had no years; wrote external fallback")
            return _upsert_annual_rows(db, company, ext_rows)
        return 0

    # 10) Upsert rows
    rows_written = 0
    for y in years:
        values = {
            "company_id": company.id,
            "fiscal_year": int(y),
            "fiscal_period": "FY",
            "source": "sec",

            # Income Statement
            "revenue": rev_map.get(y),
            "cost_of_revenue": cogs_map.get(y),
            "gross_profit": gp_map.get(y),
            "research_and_development": rnd_map.get(y),
            "selling_general_admin": sga_map.get(y),
            "sales_and_marketing": sales_marketing_map.get(y),
            "general_and_administrative": gna_map.get(y),
            "operating_income": op_map.get(y),
            "interest_expense": int_map.get(y),
            "other_income_expense": other_map.get(y),
            "income_tax_expense": tax_map.get(y),
            "net_income": ni_map.get(y),

            # Balance Sheet
            "assets_total": assets_map.get(y),
            "liabilities_current": liab_cur_map.get(y),
            "liabilities_longterm": liab_lt_map.get(y),
            "equity_total": equity_map.get(y),
            "inventories": inv_map.get(y),
            "accounts_receivable": ar_map.get(y),
            "accounts_payable": ap_map.get(y),
            "cash_and_sti": cash_sti_map.get(y),
            "total_debt": debt_map.get(y),
            "shares_outstanding": shares_map.get(y),

            # Cash Flow
            "cfo": ocf_map.get(y),
            "capex": capex_map.get(y),
            "depreciation_amortization": dep_map.get(y),
            "share_based_comp": sbc_map.get(y),
            "dividends_paid": div_map.get(y),
            "share_repurchases": rep_map.get(y),
        }

        stmt = pg_insert(FinancialAnnual).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[FinancialAnnual.company_id, FinancialAnnual.fiscal_year],
              set_={
                "revenue": stmt.excluded.revenue,
                "net_income": stmt.excluded.net_income,
                "cash_and_sti": stmt.excluded.cash_and_sti,
                "total_debt": stmt.excluded.total_debt,
                "cfo": stmt.excluded.cfo,
                "capex": stmt.excluded.capex,
                "shares_outstanding": stmt.excluded.shares_outstanding,
                "gross_profit": stmt.excluded.gross_profit,
                "operating_income": stmt.excluded.operating_income,
                "assets_total": stmt.excluded.assets_total,
                "equity_total": stmt.excluded.equity_total,
                "cost_of_revenue": stmt.excluded.cost_of_revenue,
                "research_and_development": stmt.excluded.research_and_development,
                "selling_general_admin": stmt.excluded.selling_general_admin,
                "sales_and_marketing": stmt.excluded.sales_and_marketing,
                "general_and_administrative": stmt.excluded.general_and_administrative,
                "interest_expense": stmt.excluded.interest_expense,
                "other_income_expense": stmt.excluded.other_income_expense,
                "income_tax_expense": stmt.excluded.income_tax_expense,
                "liabilities_current": stmt.excluded.liabilities_current,
                "liabilities_longterm": stmt.excluded.liabilities_longterm,
                "inventories": stmt.excluded.inventories,
                "accounts_receivable": stmt.excluded.accounts_receivable,
                "accounts_payable": stmt.excluded.accounts_payable,
                "depreciation_amortization": stmt.excluded.depreciation_amortization,
                "share_based_comp": stmt.excluded.share_based_comp,
                "dividends_paid": stmt.excluded.dividends_paid,
                "share_repurchases": stmt.excluded.share_repurchases,
                "source": stmt.excluded.source,
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
