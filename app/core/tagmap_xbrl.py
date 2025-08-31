"""Preferred US‑GAAP tag hints for core concepts.

Purpose
-------
When parsing SEC `companyfacts`, many concepts have multiple plausible tags.
This small map gives the **preferred order** to try when populating
`financials_annual`. You can expand or tune this list as you encounter
edge-cases and company-specific extensions.

Usage
-----
- For each concept (e.g., 'revenue'), iterate the list in order and pick the
  first tag that yields clean **annual USD** values.
- If all preferred tags fail, consider a fallback resolver that searches for
  company-specific extensions (e.g., `<ticker>:RevenueCustom`) and logs the
  chosen tag into `fact_provenance`.

Notes
-----
- Keep tags conservative; avoid overly-broad concepts that can double‑count.
- The keys below correspond to columns in `financials_annual` or useful inputs
  for metrics.
"""

PREFERRED_TAGS: dict[str, list[str]] = {
    # Income statement
    "revenue": [
        "us-gaap:SalesRevenueNet",
        "us-gaap:Revenues",
    ],
    "net_income": [
        "us-gaap:NetIncomeLoss",
    ],
    "gross_profit": [
        "us-gaap:GrossProfit",
    ],
    "operating_income": [
        "us-gaap:OperatingIncomeLoss",
    ],

    # Cash & investments
    "cash_and_sti": [
        "us-gaap:CashCashEquivalentsAndShortTermInvestments",
        "us-gaap:CashAndCashEquivalentsAtCarryingValue",
    ],
    "short_term_investments": [
        "us-gaap:ShortTermInvestments",
    ],

    # Debt
    "short_term_debt": [
        "us-gaap:LongTermDebtCurrent",
        "us-gaap:ShortTermBorrowings",
    ],
    "long_term_debt": [
        "us-gaap:LongTermDebtNoncurrent",
    ],

    # Shares / EPS inputs
    "shares_diluted": [
        "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",
    ],

    # Cash flow & capex
    "cfo": [
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
    ],
    "capex": [
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
    ],

    # Balance sheet totals
    "assets_total": [
        "us-gaap:Assets",
    ],
    "equity_total": [
        "us-gaap:StockholdersEquity",
    ],

    # Capital returns (optional metrics)
    "dividends_paid": [
        "us-gaap:PaymentsOfDividends",
    ],
    "buybacks": [
        "us-gaap:PaymentsForRepurchaseOfCommonStock",
    ],
}

__all__ = ["PREFERRED_TAGS"]
