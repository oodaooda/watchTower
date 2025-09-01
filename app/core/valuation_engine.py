from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict

@dataclass
class DCFParams:
    years: int = 10
    discount_rate: float = 0.10
    start_growth: float = 0.05
    terminal_growth: float = 0.025

def _df(r: float, t: int) -> float:
    return (1.0 + r) ** (-t)

def build_projections(
    base_fcf: float,
    base_year: int,
    params: DCFParams,
) -> Tuple[List[Dict], float, float, float, float]:
    """
    Returns:
      (projections, pv_explicit, terminal_value, terminal_value_pv, pv_operating)
    projections: [{year, fcf, growth, discount_factor, pv_fcf}, ...]
    """
    N = params.years
    r = params.discount_rate
    g0 = params.start_growth
    gT = params.terminal_growth

    years = list(range(1, N + 1))
    fade = (gT - g0) / max(N - 1, 1)  # linear fade from g0 to gT over N years

    projections: List[Dict] = []
    fcf = base_fcf
    pv_explicit = 0.0
    g = g0
    for k in years:
        if k == 1:
            fcf = base_fcf * (1.0 + g)
        else:
            g = g + fade
            fcf = projections[-1]["fcf"] * (1.0 + g)
        df = _df(r, k)
        pv_fcf = fcf * df
        pv_explicit += pv_fcf
        projections.append(
            {
                "year": base_year + k,
                "fcf": fcf,
                "growth": g,
                "discount_factor": df,
                "pv_fcf": pv_fcf,
            }
        )

    # Terminal (Gordon) at year N
    tv = projections[-1]["fcf"] * (1.0 + gT) / (r - gT) if r > gT else 0.0
    tv_pv = tv * _df(r, N)
    pv_oper = pv_explicit + tv_pv
    return projections, pv_explicit, tv, tv_pv, pv_oper

def equity_snapshot(
    *,
    base_fcf: Optional[float],
    cash_and_sti: Optional[float],
    total_debt: Optional[float],
    shares_outstanding: Optional[float],
    market_price: Optional[float],
    base_year: int,
    params: DCFParams,
) -> Dict:
    if base_fcf is None:
        return {
            "projections": [],
            "terminal_value": None,
            "terminal_value_pv": None,
            "enterprise_value": None,
            "equity_value": None,
            "fair_value_per_share": None,
            "upside_vs_price": None,
        }

    projections, pv_explicit, tv, tv_pv, pv_oper = build_projections(
        base_fcf=base_fcf, base_year=base_year, params=params
    )
    enterprise_value = pv_oper
    net_cash = (cash_and_sti or 0.0) - (total_debt or 0.0)
    equity_value = enterprise_value + net_cash
    per_share = (equity_value / shares_outstanding) if shares_outstanding else None
    upside = None
    if market_price and market_price > 0 and per_share is not None:
        upside = (per_share - market_price) / market_price

    return {
        "projections": projections,
        "terminal_value": tv,
        "terminal_value_pv": tv_pv,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "fair_value_per_share": per_share,
        "upside_vs_price": upside,
        "pv_operating": pv_oper,
    }
