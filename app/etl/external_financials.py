from __future__ import annotations

import datetime as dt
import requests
from typing import Dict, List, Any

YAHOO_URL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules={modules}"

EXCHANGE_SUFFIX_GUESSES = [
    ".V",   # TSXV
    ".TO",  # TSX
    ".NE",  # NEO
    ".AX",  # ASX
    ".L",   # LSE
    ".HK",  # HKEX
    ".SW",  # SIX
    ".CO",  # Copenhagen
    ".HE",  # Helsinki
    ".ST",  # Stockholm
    ".PA",  # Paris
    ".F",   # Frankfurt
    ".DE",  # Xetra/Frankfurt
    ".SI",  # Singapore
]

MANUAL_TICKER_MAP = {
    # Add known manual Yahoo Finance symbols here when base ticker fails
    "UTX": ["UTX.V", "UTX.TO", "UTX"],
}

def _get_raw(val: Any) -> float | None:
    if isinstance(val, dict) and "raw" in val:
        return float(val["raw"])
    try:
        return float(val)
    except Exception:
        return None


def _year_from_enddate(item: Dict[str, Any]) -> int | None:
    end = item.get("endDate", {})
    raw = end.get("raw") if isinstance(end, dict) else None
    if not raw:
        return None
    try:
        return dt.datetime.utcfromtimestamp(raw).year
    except Exception:
        return None


def fetch_yahoo_annual(ticker: str) -> List[Dict[str, Any]]:
    """Fetch a minimal set of annual fundamentals from Yahoo Finance (unofficial).

    Returns a list of {fiscal_year, source, ...} dicts suitable for FinancialAnnual.
    """
    modules = ",".join(
        [
            "incomeStatementHistory",
            "balanceSheetHistory",
            "cashflowStatementHistory",
            "defaultKeyStatistics",
            "financialData",
        ]
    )
    url = YAHOO_URL.format(ticker=ticker, modules=modules)
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    result = (data or {}).get("quoteSummary", {}).get("result")
    if not result:
        return []
    blob = result[0]

    # Collect per-year dicts
    per_year: Dict[int, Dict[str, Any]] = {}

    for stmt in (blob.get("incomeStatementHistory", {}) or {}).get("incomeStatementHistory", []) or []:
        year = _year_from_enddate(stmt)
        if year is None:
            continue
        per_year.setdefault(year, {})
        per_year[year]["revenue"] = _get_raw(stmt.get("totalRevenue"))
        per_year[year]["net_income"] = _get_raw(stmt.get("netIncome"))
        per_year[year]["cost_of_revenue"] = _get_raw(stmt.get("costOfRevenue"))
        per_year[year]["gross_profit"] = _get_raw(stmt.get("grossProfit"))
        per_year[year]["research_and_development"] = _get_raw(stmt.get("researchDevelopment"))
        per_year[year]["selling_general_admin"] = _get_raw(stmt.get("sellingGeneralAdministrative"))
        per_year[year]["operating_income"] = _get_raw(stmt.get("totalOperatingIncome") or stmt.get("operatingIncome"))

    for stmt in (blob.get("balanceSheetHistory", {}) or {}).get("balanceSheetStatements", []) or []:
        year = _year_from_enddate(stmt)
        if year is None:
            continue
        per_year.setdefault(year, {})
        per_year[year]["assets_total"] = _get_raw(stmt.get("totalAssets"))
        per_year[year]["liabilities_current"] = _get_raw(stmt.get("totalCurrentLiabilities"))
        per_year[year]["liabilities_longterm"] = _get_raw(stmt.get("longTermLiabilities"))
        per_year[year]["equity_total"] = _get_raw(stmt.get("totalStockholderEquity"))
        per_year[year]["cash_and_sti"] = _get_raw(
            stmt.get("cashAndShortTermInvestments") or stmt.get("cash")
        )
        per_year[year]["total_debt"] = _get_raw(
            stmt.get("shortLongTermDebt")
        ) or _get_raw(stmt.get("longTermDebt")) or _get_raw(stmt.get("totalDebt"))

    for stmt in (blob.get("cashflowStatementHistory", {}) or {}).get("cashflowStatements", []) or []:
        year = _year_from_enddate(stmt)
        if year is None:
            continue
        per_year.setdefault(year, {})
        per_year[year]["cfo"] = _get_raw(stmt.get("totalCashFromOperatingActivities"))
        per_year[year]["capex"] = _get_raw(stmt.get("capitalExpenditures"))
        per_year[year]["depreciation_amortization"] = _get_raw(stmt.get("depreciation"))

    # Shares and debt from other modules
    shares = _get_raw((blob.get("defaultKeyStatistics", {}) or {}).get("sharesOutstanding"))
    debt_fallback = _get_raw((blob.get("financialData", {}) or {}).get("totalDebt"))
    if debt_fallback is not None:
        for year in per_year:
            per_year[year].setdefault("total_debt", debt_fallback)
    if shares is not None:
        for year in per_year:
            per_year[year].setdefault("shares_outstanding", shares)

    out = []
    for year, fields in per_year.items():
        fields["fiscal_year"] = year
        fields["fiscal_period"] = "FY"
        fields["source"] = "external_yahoo"
        out.append(fields)

    return out


def fetch_yahoo_annual_variants(ticker: str, exchange_hint: str | None = None) -> List[Dict[str, Any]]:
    """Try multiple Yahoo ticker variants (base + common suffixes)."""
    tried = set()
    # If we have an exchange hint, try a mapped suffix first
    hints = []
    if exchange_hint:
        ex = exchange_hint.upper()
        if ex in ("TSX", "TSXV", "CNSX", "CNQ"):
            hints.append(".TO")
        elif ex in ("ASX",):
            hints.append(".AX")
        elif ex in ("LSE",):
            hints.append(".L")
        elif ex in ("HKEX",):
            hints.append(".HK")
    manual = MANUAL_TICKER_MAP.get(ticker.upper(), [])
    candidates = manual + [ticker] + hints + EXCHANGE_SUFFIX_GUESSES
    for suffix in candidates:
        sym = ticker if suffix == ticker else ticker + suffix if suffix.startswith(".") else suffix
        if sym in tried:
            continue
        tried.add(sym)
        rows = fetch_yahoo_annual(sym)
        if rows:
            # annotate source symbol for debugging
            for r in rows:
                r["source_symbol"] = sym
            return rows
    return []
