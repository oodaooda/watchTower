"""Financials router

Returns company-level **annual raw fundamentals** as stored in `financials_annual`,
expanded for UI-friendly Financials tabs: Income Statement, Balance Sheet, Cash Flow.

Notes:
- We coalesce alternate column names (e.g., operating_cash_flow → cfo) to
  tolerate minor schema drift without migrations.
- We compute:
    * FCF  = CFO - CapEx   (when both present)
    * EPS  = Net Income / Shares Outstanding (proxy if diluted not available)
"""
from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import FinancialAnnual, FinancialQuarterly
from app.core.schemas import FinancialAnnualOut, FinancialQuarterlyOut

router = APIRouter()

def _num(v: Optional[object]) -> Optional[float]:
    return float(v) if v is not None else None

def _coalesce(*vals):
    for v in vals:
        if v is not None:
            return v
    return None



@router.get("/quarterly/{company_id}", response_model=List[FinancialQuarterlyOut])
def get_quarterly(company_id: int, db: Session = Depends(get_db)):
    q = (
        select(FinancialQuarterly)
        .where(FinancialQuarterly.company_id == company_id)
        .order_by(FinancialQuarterly.fiscal_year.desc(), FinancialQuarterly.fiscal_period.desc())
        .limit(16)
    )
    rows = db.scalars(q).all()
    return list(reversed(rows))  # oldest -> newest

@router.get("/{company_id}", response_model=List[FinancialAnnualOut])
def company_financials(
    company_id: int = Path(..., description="Numeric company primary key (companies.id)"),
    db: Session = Depends(get_db),
):
    stmt = (
        select(FinancialAnnual)
        .where(FinancialAnnual.company_id == company_id)
        .order_by(FinancialAnnual.fiscal_year)
    )
    rows = db.scalars(stmt).all()

    out: List[FinancialAnnualOut] = []
    for r in rows:
        # --- Income Statement ---
        revenue           = _num(getattr(r, "revenue", None))
        gross_profit      = _num(getattr(r, "gross_profit", None))          # may not exist in table → None
        operating_income  = _num(getattr(r, "operating_income", None))      # may not exist in table → None
        net_income        = _num(getattr(r, "net_income", None))

        # Shares (diluted not explicitly modeled; use shares_outstanding proxy)
        shares_outstanding = _num(getattr(r, "shares_outstanding", None))
        eps_diluted = None
        if net_income is not None and shares_outstanding and shares_outstanding > 0:
            eps_diluted = net_income / shares_outstanding

        # --- Balance Sheet ---
        assets_total  = _num(getattr(r, "assets_total", None))              # may not exist in table → None
        equity_total  = _num(getattr(r, "equity_total", None))              # may not exist in table → None
        cash_and_sti  = _num(getattr(r, "cash_and_sti", None))
        total_debt    = _num(getattr(r, "total_debt", None))

        # --- Cash Flow (coalesce supported column names) ---
        cfo_val   = _coalesce(getattr(r, "cfo", None), getattr(r, "operating_cash_flow", None))
        capex_val = _coalesce(getattr(r, "capex", None), getattr(r, "capital_expenditures", None))
        cfo  = _num(cfo_val)
        capex = _num(capex_val)
        fcf = (cfo - capex) if (cfo is not None and capex is not None) else None

        out.append(
            FinancialAnnualOut(
                fiscal_year=int(r.fiscal_year),

                # Income Statement
                revenue=revenue,
                gross_profit=gross_profit,
                operating_income=operating_income,
                net_income=net_income,
                eps_diluted=eps_diluted,

                # Balance Sheet
                assets_total=assets_total,
                equity_total=equity_total,
                cash_and_sti=cash_and_sti,
                total_debt=total_debt,
                shares_outstanding=shares_outstanding,

                # Cash Flow
                cfo=cfo,
                capex=capex,
                fcf=fcf,
            )
        )

    return out
