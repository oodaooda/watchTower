"""Metric computation helpers

Pure-python utilities to compute derived metrics used by the screening API.
These functions are small, testable building blocks that operate on Python
numbers/lists and return `float|int|None` with safe divide-by-zero handling.

Included:
- `safe_div(a,b)` — null/zero-safe division
- `yoy(series)` — year-over-year growth list from a numeric series
- `cagr(series, years)` — trailing CAGR over `years` if enough data
- `growth_consistency(rev, ni, window)` — count of years (within window)
   where **both revenue and net income increased** vs prior year
- `cash_debt_ratio(cash, debt)` — cash & short-term investments / total debt
- `piotroski_f_score(flags)` — simple scaffold that sums 9 boolean tests
- `altman_z_public_mfg(X)` — classic Z formula given inputs X1..X5

Design notes:
- Treat negative/zero denominators as `None` where undefined.
- Return `None` if inputs are insufficient; callers can decide how to default.
- Keep this module independent of pandas/SQLAlchemy to simplify unit tests.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


# -----------------------------
# Utilities
# -----------------------------

def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Divide `a/b` with `None` for invalid/zero cases."""
    try:
        if a is None or b is None or b == 0:
            return None
        return float(a) / float(b)
    except Exception:
        return None


def yoy(series: List[Optional[float]]) -> List[Optional[float]]:
    """Compute year-over-year growth for a numeric series.

    For the first element or missing neighbors, returns `None`.
    """
    out: List[Optional[float]] = []
    for i, v in enumerate(series):
        if i == 0 or v is None or series[i - 1] is None:
            out.append(None)
        else:
            prev = series[i - 1]
            out.append(safe_div(v - prev, prev))
    return out


def cagr(series: List[Optional[float]], years: int) -> Optional[float]:
    """Compute trailing CAGR over `years` using the earliest and latest
    available non-null values at least `years` apart.
    """
    if len(series) < years + 1:
        return None

    # Find last index with a value
    end_idx = None
    for i in range(len(series) - 1, -1, -1):
        if series[i] is not None and series[i] > 0:
            end_idx = i
            break
    if end_idx is None:
        return None

    start_idx = end_idx - years
    if start_idx < 0 or series[start_idx] is None or series[start_idx] <= 0:
        return None

    try:
        return (series[end_idx] / series[start_idx]) ** (1 / years) - 1
    except Exception:
        return None



def growth_consistency(
    revenue_series: List[Optional[float]],
    ni_series: List[Optional[float]],
    window: int = 10,
) -> Optional[int]:
    """Count years in the trailing `window` where **both** revenue and net income
    increased vs the previous year.
    """
    if not revenue_series or not ni_series:
        return None
    n = min(len(revenue_series), len(ni_series))
    # Only consider the last `window`+1 points (we need neighbors)
    rev = revenue_series[-(window + 1) :] if n >= window + 1 else revenue_series
    ni = ni_series[-(window + 1) :] if n >= window + 1 else ni_series

    count = 0
    for i in range(1, min(len(rev), len(ni))):
        r0, r1 = rev[i - 1], rev[i]
        n0, n1 = ni[i - 1], ni[i]
        if r0 is None or r1 is None or n0 is None or n1 is None:
            continue
        if r1 > r0 and n1 > n0:
            count += 1
    return count


def cash_debt_ratio(cash_and_sti: Optional[float], total_debt: Optional[float]) -> Optional[float]:
    """Compute cash & short-term investments to total debt."""
    return safe_div(cash_and_sti, total_debt)


# -----------------------------
# Scores (scaffolds)
# -----------------------------

def piotroski_f_score(flags: Dict[str, Any]) -> Optional[int]:
    """Sum the 9 Piotroski binary tests.

    Expected keys (bools):
    - profit_pos, cfo_pos, roa_improve, accruals_good,
    - leverage_down, liquidity_up, no_dilution,
    - margin_up, asset_turnover_up
    """
    keys = [
        "profit_pos",
        "cfo_pos",
        "roa_improve",
        "accruals_good",
        "leverage_down",
        "liquidity_up",
        "no_dilution",
        "margin_up",
        "asset_turnover_up",
    ]
    score = 0
    for k in keys:
        if flags.get(k) is True:
            score += 1
    return score


def altman_z_public_mfg(X: Dict[str, Optional[float]]) -> Optional[float]:
    """Altman Z (public manufacturing) given inputs X1..X5.

    Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
    where:
      X1 = Working Capital / Total Assets
      X2 = Retained Earnings / Total Assets
      X3 = EBIT / Total Assets
      X4 = Market Value of Equity / Total Liabilities
      X5 = Sales / Total Assets
    Returns `None` if any input missing.
    """
    try:
        return (
            1.2 * float(X["X1"]) +
            1.4 * float(X["X2"]) +
            3.3 * float(X["X3"]) +
            0.6 * float(X["X4"]) +
            1.0 * float(X["X5"])
        )
    except Exception:
        return None


# -----------------------------
# Example: build per-year metrics from series
# -----------------------------

def build_metrics_rows(
    fiscal_years: List[int],
    revenue: List[Optional[float]],
    net_income: List[Optional[float]],
    cash_and_sti: List[Optional[float]],
    total_debt: List[Optional[float]],
    ttm_eps: List[Optional[float]] | None = None,
) -> List[Dict[str, Optional[float]]]:
    """Compute per-year metrics; always return one row per fiscal year.

    Missing inputs produce None for that metric, but the row is still emitted.
    """
    n = len(fiscal_years)
    out: List[Dict[str, Optional[float]]] = []

    rev_yoy_list = yoy(revenue)
    ni_yoy_list = yoy(net_income)

    for i in range(n):
        year = fiscal_years[i]
        cash = cash_and_sti[i] if i < len(cash_and_sti) else None
        debt = total_debt[i] if i < len(total_debt) else None

        row = {
            "fiscal_year": year,
            "cash_debt_ratio": cash_debt_ratio(cash, debt),
            "rev_yoy": rev_yoy_list[i] if i < len(rev_yoy_list) else None,
            "ni_yoy": ni_yoy_list[i] if i < len(ni_yoy_list) else None,
            "rev_cagr_5y": cagr(revenue[: i + 1], 5),
            "ni_cagr_5y": cagr(net_income[: i + 1], 5),
            "growth_consistency": growth_consistency(
                revenue[: i + 1], net_income[: i + 1], window=10
            ),
            "ttm_eps": ttm_eps[i] if (ttm_eps and i < len(ttm_eps)) else None,
        }

        # ✅ Always append row (don’t skip if mostly None)
        out.append(row)

    return out



__all__ = [
    "safe_div",
    "yoy",
    "cagr",
    "growth_consistency",
    "cash_debt_ratio",
    "piotroski_f_score",
    "altman_z_public_mfg",
    "build_metrics_rows",
]
