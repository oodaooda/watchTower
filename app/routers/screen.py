"""Screening endpoint

Returns companies matching value-style filters:
- low P/E (FY-based proxy for now),
- strong cash/debt,
- consistent growth, etc.

How it works:
1) Start from tracked companies.
2) Join to latest-year metrics_annual (or a specific year if provided).
3) LEFT JOIN prices_annual for P/E (may be NULL).
4) Apply filters and sort.
"""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, Float, select, func, and_, desc
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Company, MetricsAnnual, PriceAnnual
from app.core.schemas import ScreenResultItem

# Mounted at /screen
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
    growth_min = growth_consistency_min if growth_consistency_min is not None else growth_consistency_gte

    c, m, p = Company, MetricsAnnual, PriceAnnual

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
        cast(p.pe_ttm, Float).label("pe_ttm"),
        c.cik.label("cik"), #added
    )

    stmt = select(*cols).select_from(c).where(c.is_tracked.is_(True))

    if year is None:
        latest = (
            select(m.company_id, func.max(m.fiscal_year).label("latest_year"))
            .group_by(m.company_id)
            .subquery()
        )
        stmt = (
            stmt.join(latest, latest.c.company_id == c.id)
                .join(m, (m.company_id == c.id) & (m.fiscal_year == latest.c.latest_year))
        )
    else:
        stmt = stmt.join(m, (m.company_id == c.id) & (m.fiscal_year == year))

    stmt = stmt.join(p, (p.company_id == c.id) & (p.fiscal_year == m.fiscal_year), isouter=True)

    filters = []
    if industry:
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

    stmt = stmt.order_by(
        p.pe_ttm.asc().nulls_last(),
        desc(m.cash_debt_ratio),
        c.ticker.asc(),
    ).limit(limit).offset(offset)

    rows = db.execute(stmt).mappings().all()
    return [ScreenResultItem(**dict(r)) for r in rows]