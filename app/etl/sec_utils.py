"""Shared SEC utilities for annual and quarterly backfills."""

from typing import Dict, List, Tuple
from app.etl.sec_fetch_companyfacts import (
    extract_annual_usd_facts,
    extract_quarterly_usd_facts,
    list_available_tags, )


# ----------------------------
# Tag preference lists
# ----------------------------
REV_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"]
NI_TAGS = ["NetIncomeLoss"]
CFO_TAGS = ["NetCashProvidedByUsedInOperatingActivities"]
CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment"]

COGS_TAGS = ["CostOfRevenue"]
GP_TAGS = ["GrossProfit"]
RND_TAGS = ["ResearchAndDevelopmentExpense"]
SGA_TAGS = ["SellingGeneralAndAdministrativeExpense"]
OPINC_TAGS = ["OperatingIncomeLoss"]
INTEXP_TAGS = [
    "InterestExpense",
    "InterestExpenseDebt",
    "InterestExpenseDebtExcludingAmortization",
    "InterestExpenseNonoperating",
    "FinanceLeaseInterestExpense",
]
TAXEXP_TAGS = ["IncomeTaxExpenseBenefit"]

ASSETS_TAGS = ["Assets"]
LIABC_TAGS = ["LiabilitiesCurrent"]
LIABLT_TAGS = ["LongTermLiabilitiesNoncurrent"]
EQUITY_TAGS = ["StockholdersEquity"]
INV_TAGS = ["InventoryNet"]
AR_TAGS = ["AccountsReceivableNetCurrent"]
AP_TAGS = ["AccountsPayableCurrent"]
CASH_TAGS = ["CashCashEquivalentsAndShortTermInvestments"]
DEBT_TAGS = ["Debt"]
SHARES_TAGS = ["CommonStockSharesOutstanding"]

DEP_TAGS = ["DepreciationAndAmortization"]
SBC_TAGS = ["ShareBasedCompensation"]
DIV_TAGS = ["PaymentsOfDividends"]
REP_TAGS = ["PaymentsForRepurchaseOfCommonStock"]

# ----------------------------
# Fallback keywords
# ----------------------------
FALLBACK_KEYWORDS = {
    "revenue": ["revenue", "sales"],
    "net_income": ["netincome", "netincomeloss", "profitloss"],
    "cfo": ["operatingactivities", "operatingcashflow"],
    "capex": ["capitalexpenditure", "purchaseofproperty"],
    "cost_of_revenue": ["costofrevenue", "costofgoods", "costofgoodsandservicessold"],
    "gross_profit": ["grossprofit","GrossProfit"],
    "research_and_development": ["researchanddevelopment", "rdexpense"],
    "selling_general_admin": ["sellinggeneral", "sga", "administrative", "sellinggeneralandadministrative"],
    "operating_income": ["operatingincome", "operatingincomeloss"],
    "interest_expense": ["interestexpense", "interestexpensedebt"],
    "income_tax_expense": ["incometax", "taxexpense"],
    "assets_total": ["assets", "total"],
    "liabilities_current": ["liabilities", "current"],
    "liabilities_longterm": ["liabilities", "longterm"],
    "equity_total": ["stockholders", "equity"],
    "inventories": ["inventory"],
    "accounts_receivable": ["accounts", "receivable"],
    "accounts_payable": ["accounts", "payable"],
    "cash_and_sti": ["cash", "shortterminvestments"],
    "total_debt": ["total", "debt"],
    "shares_outstanding": ["shares", "outstanding"],
    "depreciation_amortization": [
        "depreciation",
        "amortization",
        "depreciationandamortization",
        "depreciationamortizationandaccretionnet"
    ],
    "share_based_comp": ["sharebasedcompensation", "allocatedsharebasedcompensationexpense"],
    "dividends_paid": ["dividend", "paymentsofdividends", "commonstockdividendspersharecashpaid"],
    "share_repurchases": ["repurchase", "buyback", "paymentsforrepurchaseofcommonstock"],
}


# ----------------------------
# Tag preference lists
# ----------------------------

REV_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
    "SalesRevenueGoodsNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    # alternates
    "TotalRevenue",
    "OperatingRevenue",
    "RevenuesNetOfInterestExpense",
]

NI_TAGS = [
    "NetIncomeLoss",
    # alternates
    "ProfitLoss",
    "NetEarnings",
]

CASH_STI_AGG = ["CashCashEquivalentsAndShortTermInvestments"]
CASH_ONLY = ["CashAndCashEquivalentsAtCarryingValue"]
STI_ONLY = ["ShortTermInvestments", "MarketableSecuritiesCurrent"]

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

OCF_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]

CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "CapitalExpenditures",
    "PaymentsToAcquirePropertyPlantAndEquipmentContinuingOperations",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquirePropertyPlantAndEquipmentExcludingLeasedAssets",
    "PurchaseOfPropertyAndEquipment",
    "PurchasesOfPropertyAndEquipment",
]

COGS_TAGS = [
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "CostOfGoodsSold",
]

GROSS_PROFIT_TAGS = [
    "GrossProfit",
    "GrossIncome",
]

RND_TAGS = [
    "ResearchAndDevelopmentExpense",
    "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
]

SGA_TAGS = [
    "SellingGeneralAndAdministrativeExpense",
    "SellingAndMarketingExpense",
    "GeneralAndAdministrativeExpense",
    "SellingGeneralAdministrativeAndOtherExpenses",
]

OPERATING_INCOME_TAGS = [
    "OperatingIncomeLoss",
    "OperatingProfitLoss",
]

INT_EXP_TAGS = [
    "InterestExpense",
    "InterestExpenseDebt",
]

TAX_EXP_TAGS = [
    "IncomeTaxExpenseBenefit",
    "IncomeTaxExpenseBenefitContinuingOperations",
]

DEP_AMORT_TAGS = ["DepreciationAndAmortization"]
SBC_TAGS = ["ShareBasedCompensation"]
DIVIDENDS_TAGS = ["PaymentsOfDividends", "DividendsPaid"]
REPURCHASE_TAGS = ["PaymentsForRepurchaseOfCommonStock", "ShareRepurchase"]

ASSETS_TAGS = ["Assets", "AssetsTotal"]
LIAB_CURRENT_TAGS = ["LiabilitiesCurrent", "CurrentLiabilities"]
LIAB_LT_TAGS = ["LongTermLiabilitiesNoncurrent", "LiabilitiesNoncurrent"]
EQUITY_TAGS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
INVENTORIES_TAGS = ["InventoryNet"]
AR_TAGS = ["AccountsReceivableNetCurrent"]
AP_TAGS = ["AccountsPayableCurrent"]

SHARES_TAGS = ["CommonStockSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"]

# ----------------------------
# Helpers
# ----------------------------

def series_to_map(series: List[dict], period_type: str = "annual", derive_q4: bool = True) -> Dict:
    """Convert SEC fact series -> {fiscal_key: value}.

    - Annual → keep FY values.
    - Quarterly → keep Q1, Q2, Q3, derive Q4 from FY - (Q1+Q2+Q3), drop FY.
    """
    out = {}

    if period_type == "annual":
        # keep FY values for annual mode
        for x in series:
            if x.get("fy") and x.get("val") is not None:
                out[(int(x["fy"]), "FY")] = float(x["val"])
    else:
        tmp = {}
        for x in series:
            fy = x.get("fy")
            fp = x.get("fp")
            val = x.get("val")
            if not fy or val is None:
                continue
            fy = int(fy)
            if fp in ("Q1", "Q2", "Q3", "Q4"):
                tmp[(fy, fp)] = float(val)
            elif fp == "FY":
                tmp[(fy, "FY")] = float(val)

        for fy in {k[0] for k in tmp.keys()}:
            if derive_q4:
                fy_val = tmp.get((fy, "FY"))
                if fy_val is not None:
                    q1 = tmp.get((fy, "Q1"), 0)
                    q2 = tmp.get((fy, "Q2"), 0)
                    q3 = tmp.get((fy, "Q3"), 0)
                    q4_val = fy_val - (q1 + q2 + q3)
                    out[(fy, "Q4")] = q4_val
            else:
                if (fy, "Q4") in tmp:
                    out[(fy, "Q4")] = tmp[(fy, "Q4")]
                elif (fy, "FY") in tmp:
                    out[(fy, "Q4")] = tmp[(fy, "FY")]

            for q in ("Q1", "Q2", "Q3"):
                if (fy, q) in tmp:
                    out[(fy, q)] = tmp[(fy, q)]

    return out




def add_series(a_map: Dict[int, float], b_map: Dict[int, float]) -> Dict[int, float]:
    """Elementwise add two FY maps (missing -> 0)."""
    years = set(a_map) | set(b_map)
    return {y: (a_map.get(y, 0.0) or 0.0) + (b_map.get(y, 0.0) or 0.0) for y in years}

def build_tag_maps(cf: Dict, tags: List[str], period_type: str = "annual", derive_q4: bool = True) -> Dict[str, Dict]:
    """Return {tag: {fiscal_key: val}} for each candidate tag."""
    out: Dict[str, Dict] = {}
    extractor = extract_annual_usd_facts if period_type == "annual" else extract_quarterly_usd_facts
    for t in tags:
        out[t] = series_to_map(extractor(cf, t), period_type=period_type, derive_q4=derive_q4)
    return out

def merge_by_preference(tag_maps: Dict[str, Dict], pref: List[str]) -> Tuple[str, Dict]:
    """For each fiscal period, take the first tag (by pref order) that has a value."""
    keys = set()
    for m in tag_maps.values():
        keys |= set(m.keys())

    merged = {}
    used = {t: 0 for t in pref}

    for k in sorted(keys):
        for t in pref:
            v = tag_maps.get(t, {}).get(k)
            if v is not None:
                merged[k] = v
                used[t] += 1
                break

    parts = [f"{t}({used[t]})" for t in pref if used.get(t)]
    label = "+".join(parts) if parts else "+".join(pref[:1])
    return label, merged


def keyword_fallback(cf: dict, required_words: List[str], period_type: str = "annual", derive_q4: bool = True) -> Dict:
    """Search SEC tags for one containing all required_words."""
    tags = list_available_tags(cf)
    extractor = extract_annual_usd_facts if period_type == "annual" else extract_quarterly_usd_facts

    for t in tags:
        # --- CHANGE: normalize tag to lowercase once here ---
        t_lower = t.lower()
        if all(w.lower() in t_lower for w in required_words):  # <- now consistent case-insensitive
            series = extractor(cf, t)
            if series:
                print(f"[fallback] Using tag {t} for {required_words}")
                return series_to_map(series, period_type, derive_q4)
    return {}


# ----------------------------
# Unified helper
# ----------------------------

def get_series_with_fallback(
    cf: Dict,
    preferred: List[str],
    keywords: List[str],
    period_type: str = "annual",
    derive_q4: bool = True,
) -> Dict[Tuple[int, str], float]:
    """
    Extract a fiscal series from SEC companyfacts.

    - Try candidate tags in order, selecting the first tag with a value for each period.
    - If preferred tags produce partial coverage, keep what we found but still look for
      fallback keyword matches to fill remaining gaps.
    - Ensures Q4 is synthesized from FY when we are in quarterly mode.
    """
    tag_maps = build_tag_maps(cf, preferred, period_type=period_type, derive_q4=derive_q4)
    _, merged = merge_by_preference(tag_maps, preferred)
    out: Dict[Tuple[int, str], float] = dict(merged)

    if keywords:
        fallback_map = keyword_fallback(cf, keywords, period_type=period_type, derive_q4=derive_q4)
        for key, value in fallback_map.items():
            out.setdefault(key, value)

    return out
