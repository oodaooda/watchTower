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

from fastapi import APIRouter, Depends, Path, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import FinancialAnnual, FinancialQuarterly, Company
from app.core.schemas import FinancialAnnualOut, FinancialQuarterlyOut

router = APIRouter()

def _num(v: Optional[object]) -> Optional[float]:
    return float(v) if v is not None else None

def _coalesce(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def _resolve_company(db: Session, identifier: str) -> Company | None:
    ident = (identifier or "").strip()
    if not ident:
        return None
    # Try numeric id
    try:
        cid = int(ident)
    except ValueError:
        cid = None
    if cid is not None:
        co = db.get(Company, cid)
        if co:
            return co
    # Fallback to ticker (case-insensitive)
    return db.execute(
        select(Company).where(Company.ticker == ident.upper())
    ).scalar_one_or_none()



@router.get("/quarterly/{identifier}", response_model=List[FinancialQuarterlyOut])
def get_quarterly(identifier: str, db: Session = Depends(get_db)):
    company = _resolve_company(db, identifier)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    q = (
        select(FinancialQuarterly)
        .where(FinancialQuarterly.company_id == company.id)
        .order_by(FinancialQuarterly.fiscal_year.desc(), FinancialQuarterly.fiscal_period.desc())
        .limit(16)
    )
    rows = db.scalars(q).all()
    return list(reversed(rows))  # oldest -> newest

@router.get("/{identifier}", response_model=List[FinancialAnnualOut])
def company_financials(
    identifier: str = Path(..., description="Company id or ticker symbol"),
    db: Session = Depends(get_db),
):
    company = _resolve_company(db, identifier)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    stmt = (
        select(FinancialAnnual)
        .where(FinancialAnnual.company_id == company.id)
        .order_by(FinancialAnnual.fiscal_year)
    )
    rows = db.scalars(stmt).all()

    out: List[FinancialAnnualOut] = []
    for r in rows:
        # --- Income Statement ---
        revenue           = _num(getattr(r, "revenue", None))
        cost_of_revenue   = _num(getattr(r, "cost_of_revenue", None))
        gross_profit      = _num(getattr(r, "gross_profit", None))          # may not exist in table → None
        research_and_development = _num(getattr(r, "research_and_development", None))
        selling_general_admin    = _num(getattr(r, "selling_general_admin", None))
        sales_and_marketing      = _num(getattr(r, "sales_and_marketing", None))
        general_and_administrative = _num(getattr(r, "general_and_administrative", None))
        operating_income  = _num(getattr(r, "operating_income", None))      # may not exist in table → None
        interest_expense  = _num(getattr(r, "interest_expense", None))
        other_income_expense = _num(getattr(r, "other_income_expense", None))
        income_tax_expense = _num(getattr(r, "income_tax_expense", None))
        net_income        = _num(getattr(r, "net_income", None))

        # Shares (diluted not explicitly modeled; use shares_outstanding proxy)
        shares_outstanding = _num(getattr(r, "shares_outstanding", None))
        eps_diluted = None
        if net_income is not None and shares_outstanding and shares_outstanding > 0:
            eps_diluted = net_income / shares_outstanding

        # --- Balance Sheet ---
        assets_total  = _num(getattr(r, "assets_total", None))              # may not exist in table → None
        liabilities_current = _num(getattr(r, "liabilities_current", None))
        liabilities_longterm = _num(getattr(r, "liabilities_longterm", None))
        equity_total  = _num(getattr(r, "equity_total", None))              # may not exist in table → None
        inventories   = _num(getattr(r, "inventories", None))
        accounts_receivable = _num(getattr(r, "accounts_receivable", None))
        accounts_payable    = _num(getattr(r, "accounts_payable", None))
        cash_and_sti  = _num(getattr(r, "cash_and_sti", None))
        total_debt    = _num(getattr(r, "total_debt", None))

        # --- Cash Flow (coalesce supported column names) ---
        cfo_val   = _coalesce(getattr(r, "cfo", None), getattr(r, "operating_cash_flow", None))
        capex_val = _coalesce(getattr(r, "capex", None), getattr(r, "capital_expenditures", None))
        cfo  = _num(cfo_val)
        capex = _num(capex_val)
        fcf = (cfo - capex) if (cfo is not None and capex is not None) else None
        depreciation_amortization = _num(getattr(r, "depreciation_amortization", None))
        share_based_comp = _num(getattr(r, "share_based_comp", None))
        dividends_paid = _num(getattr(r, "dividends_paid", None))
        share_repurchases = _num(getattr(r, "share_repurchases", None))

        out.append(
            FinancialAnnualOut(
                fiscal_year=int(r.fiscal_year),

                # Income Statement
                revenue=revenue,
                cost_of_revenue=cost_of_revenue,
                gross_profit=gross_profit,
                research_and_development=research_and_development,
                selling_general_admin=selling_general_admin,
                sales_and_marketing=sales_and_marketing,
                general_and_administrative=general_and_administrative,
                operating_income=operating_income,
                interest_expense=interest_expense,
                other_income_expense=other_income_expense,
                income_tax_expense=income_tax_expense,
                net_income=net_income,
                eps_diluted=eps_diluted,

                # Balance Sheet
                assets_total=assets_total,
                liabilities_current=liabilities_current,
                liabilities_longterm=liabilities_longterm,
                equity_total=equity_total,
                inventories=inventories,
                accounts_receivable=accounts_receivable,
                accounts_payable=accounts_payable,
                cash_and_sti=cash_and_sti,
                total_debt=total_debt,
                shares_outstanding=shares_outstanding,

                # Cash Flow
                cfo=cfo,
                capex=capex,
                fcf=fcf,
                depreciation_amortization=depreciation_amortization,
                share_based_comp=share_based_comp,
                dividends_paid=dividends_paid,
                share_repurchases=share_repurchases,
            )
        )

    return out
