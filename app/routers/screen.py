"""Screening endpoint

Returns companies matching value-style filters:
- low P/E (FY-based proxy for now),
- strong cash/debt,
- consistent growth, etc.

How it works:
1) Start from tracked companies.
2) Join to latest-year metrics_annual (or a specific year if provided).
3) LEFT JOIN the **latest** prices_annual row per company for P/E & price.
4) Apply filters and sort.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, Float, select, func, and_, desc
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Company, MetricsAnnual, PriceAnnual
from app.core.schemas import ScreenResultItem

from pydantic import BaseModel 


router = APIRouter(prefix="/screen", tags=["screen"])


@router.get("", response_model=List[ScreenResultItem])
def run_screen(
    pe_max: Optional[float] = Query(None, description="Maximum P/E (TTM)"),
    cash_debt_min: Optional[float] = Query(None, description="Minimum Cash/Debt"),
    cash_debt_gte: Optional[float] = Query(None, description="Alias for cash_debt_min"),
    growth_consistency_min: Optional[int] = Query(None, description="Min growth consistency"),
    growth_consistency_gte: Optional[int] = Query(None, description="Alias for growth_consistency_min"),
    rev_cagr_min: Optional[float] = Query(None, description="Min 5y rev CAGR (decimal)"),
    ni_cagr_min: Optional[float] = Query(None, description="Min 5y NI CAGR (decimal)"),
    fcf_cagr_min: Optional[float] = Query(None, description="Min 5y FCF CAGR (decimal)"),
    industry: Optional[str] = Query(None, description="Exact industry_name or SIC"),
    year: Optional[int] = Query(None, description="Specific fiscal year; else latest per company"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    # coalesce aliases
    cash_min = cash_debt_min if cash_debt_min is not None else cash_debt_gte
    growth_min = (
        growth_consistency_min
        if growth_consistency_min is not None
        else growth_consistency_gte
    )

    c, m, p = Company, MetricsAnnual, PriceAnnual

    # columns returned
    cols = (
            c.id.label("company_id"),
                c.ticker.label("ticker"),
                c.name.label("name"),
                c.industry_name.label("industry"),
                m.fiscal_year.label("fiscal_year"),
                cast(m.cash_debt_ratio, Float).label("cash_debt_ratio"),
                m.growth_consistency.label("growth_consistency"),
                cast(m.rev_cagr_5y, Float).label("rev_cagr_5y"),
                cast(m.ni_cagr_5y, Float).label("ni_cagr_5y"),
                cast(m.fcf, Float).label("fcf"),
                cast(m.fcf_cagr_5y, Float).label("fcf_cagr_5y"),
                cast(p.close_price, Float).label("price"),    # ← NEW
                cast(p.pe_ttm, Float).label("pe_ttm"),
                c.cik.label("cik"),
    )

    # base: tracked companies
    stmt = select(*cols).select_from(c).where(c.is_tracked.is_(True))

    # join metrics: latest year or a specified year
    if year is None:
        latest_metrics = (
            select(m.company_id, func.max(m.fiscal_year).label("latest_year"))
            .group_by(m.company_id)
            .subquery()
        )
        stmt = (
            stmt.join(latest_metrics, latest_metrics.c.company_id == c.id)
            .join(m, (m.company_id == c.id) & (m.fiscal_year == latest_metrics.c.latest_year))
        )
    else:
        stmt = stmt.join(m, (m.company_id == c.id) & (m.fiscal_year == year))

    # join prices: **latest** price row per company (independent of metrics year)
    latest_price = (
        select(p.company_id, func.max(p.fiscal_year).label("fy_price"))
        .group_by(p.company_id)
        .subquery()
    )
    stmt = (
        stmt.join(latest_price, latest_price.c.company_id == c.id, isouter=True)
        .join(
            p,
            (p.company_id == c.id) & (p.fiscal_year == latest_price.c.fy_price),
            isouter=True,
        )
    )

    # filters
    filters = []
    if industry:
        # allow either industry_name or SIC exact match
        filters.append((c.industry_name == industry) | (c.sic == industry))
    if pe_max is not None:
        filters.append(p.pe_ttm <= pe_max)
    if cash_min is not None:
        filters.append(m.cash_debt_ratio >= cash_min)
    if growth_min is not None:
        filters.append(m.growth_consistency >= growth_min)
    if rev_cagr_min is not None:
        filters.append(m.rev_cagr_5y >= rev_cagr_min)
    if ni_cagr_min is not None:
        filters.append(m.ni_cagr_5y >= ni_cagr_min)
    if fcf_cagr_min is not None:
        filters.append(m.fcf_cagr_5y >= fcf_cagr_min)

    if filters:
        stmt = stmt.where(and_(*filters))

    # sort & paginate
    stmt = (
        stmt.order_by(
            p.pe_ttm.asc().nulls_last(),  # lowest P/E first; nulls last
            desc(m.cash_debt_ratio),
            c.ticker.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(stmt).mappings().all()
    return [ScreenResultItem(**dict(r)) for r in rows]

