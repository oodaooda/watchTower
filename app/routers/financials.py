"""Financials router

Exposes company-level **annual raw fundamentals** as stored in `financials_annual`.
This is the source-of-truth view for revenue, net income, cash & short-term
investments, total debt, and diluted shares (one row per fiscal year).

How it works:
- The endpoint takes a `company_id` (DB PK), queries all rows for that company,
  orders them by `fiscal_year`, and returns a list of Pydantic models.
- Numbers are returned as floats (or `null`) for frontend-friendliness.
- If the company has no rows yet (e.g., not ingested), it returns an empty list
  rather than 404 (since the company may exist but data is pending).

Design notes:
- We keep this endpoint *raw* and free of derived metrics. Anything computed
  belongs in `/metrics`.
- Provenance (tag/unit/accession) is not exposed here—query the provenance table
  by `financial_id` if you need audit details in the future.
"""
from typing import List

from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import FinancialAnnual
from app.core.schemas import FinancialAnnualOut

router = APIRouter()


@router.get("/{company_id}", response_model=List[FinancialAnnualOut])
def company_financials(
    company_id: int = Path(..., description="Numeric company primary key (companies.id)"),
    db: Session = Depends(get_db),
):
    """Return **all annual raw fundamentals** for a given company.

    Each item corresponds to a fiscal year. Values may be `null` if a tag is
    missing for that year (we do not zero-fill).
    """
    stmt = (
        select(FinancialAnnual)
        .where(FinancialAnnual.company_id == company_id)
        .order_by(FinancialAnnual.fiscal_year)
    )
    rows = db.scalars(stmt).all()

    # Map ORM rows to API schema, coercing Decimals to float for JSON.
    out: List[FinancialAnnualOut] = []
    for r in rows:
        out.append(
            FinancialAnnualOut(
                fiscal_year=r.fiscal_year,
                revenue=float(r.revenue) if r.revenue is not None else None,
                net_income=float(r.net_income) if r.net_income is not None else None,
                cash_and_sti=float(r.cash_and_sti) if r.cash_and_sti is not None else None,
                total_debt=float(r.total_debt) if r.total_debt is not None else None,
                shares_diluted=float(r.shares_diluted) if r.shares_diluted is not None else None,
            )
        )

    return out
