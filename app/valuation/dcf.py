# app/valuation/dcf.py
from __future__ import annotations
from typing import Dict, List, Optional

def dcf_two_stage(
    fcf0: float,             # most recent annual FCF
    g1: float = 0.08,        # stage-1 growth (e.g., 8%)
    n: int = 5,              # years at g1
    gT: float = 0.025,       # terminal growth (e.g., 2.5%)
    r: float = 0.09,         # discount rate / WACC (e.g., 9%)
    fade: int = 5,           # years to linearly fade g1 -> gT
    net_cash: float = 0.0,   # cash - debt (can be negative)
    shares_out: Optional[float] = None,  # diluted shares for per-share
) -> Dict:
    """
    Two-stage DCF:
      - grow FCF at g1 for n years
      - linearly fade growth from g1 to gT over `fade` years
      - terminal value at end of horizon with Gordon Growth at gT
      - discount all cash flows and TV at rate r
    """
    if fcf0 is None or fcf0 <= 0 or r <= gT:
        return {"error": "Invalid inputs (fcf0<=0 or r<=gT).", "per_share": None}

    # Stage 1: constant g1 for n years
    cashflows: List[float] = []
    f = fcf0
    for _ in range(n):
        f *= (1.0 + g1)
        cashflows.append(f)

    # Stage 2: fade growth from g1 -> gT over `fade` years
    last_g = g1
    if fade > 0:
        step = (gT - g1) / float(fade)
        for _ in range(fade):
            last_g += step
            f *= (1.0 + last_g)
            cashflows.append(f)
    else:
        last_g = g1

    # Terminal value at end of horizon (last growth = gT)
    terminal = cashflows[-1] * (1.0 + gT) / (r - gT)

    # Discount back
    pv = 0.0
    for t, cf in enumerate(cashflows, start=1):
        pv += cf / ((1.0 + r) ** t)
    pv += terminal / ((1.0 + r) ** len(cashflows))

    equity = pv + (net_cash or 0.0)
    per_share = (equity / shares_out) if (shares_out and shares_out > 0) else None

    return {
        "fcf0": fcf0,
        "pv_operating": pv,
        "net_cash": net_cash,
        "equity_value": equity,
        "per_share": per_share,
        "horizon_years": len(cashflows),
        "assumptions": {"g1": g1, "n": n, "fade": fade, "gT": gT, "r": r},
        "cashflows": cashflows,
    }
