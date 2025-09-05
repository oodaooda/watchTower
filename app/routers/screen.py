# app/routers/screen.py
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, Float, select, func, and_, desc
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.models import Company, MetricsAnnual, PriceAnnual, FinancialAnnual

router = APIRouter(prefix="/screen", tags=["screen"])

@router.get("")
def run_screen(
    pe_max: Optional[float] = Query(None, description="Maximum P/E (TTM)"),
    tickers: Optional[str] = Query(None, description="Comma-separated tickers e.g. AAPL,TSLA,MSFT"),
    cash_debt_min: Optional[float] = Query(None),
    cash_debt_gte: Optional[float] = Query(None),
    growth_consistency_min: Optional[int] = Query(None),
    growth_consistency_gte: Optional[int] = Query(None),
    rev_cagr_min: Optional[float] = Query(None),
    ni_cagr_min: Optional[float] = Query(None),
    fcf_cagr_min: Optional[float] = Query(None),
    market_cap_min: Optional[float] = Query(None),
    industry: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns paginated screener results:
    {
        "total_count": int,
        "items": [ {row}, {row}, ... ]
    }
    """

    cash_min = cash_debt_min if cash_debt_min is not None else cash_debt_gte
    growth_min = growth_consistency_min if growth_consistency_min is not None else growth_consistency_gte

    c, m, p, f = Company, MetricsAnnual, PriceAnnual, FinancialAnnual

    # latest metrics year per company
    if year is None:
        latest_m = (
            select(m.company_id, func.max(m.fiscal_year).label("latest_year"))
            .group_by(m.company_id)
            .subquery()
        )
    # latest financials (for shares) per company
    latest_f = (
        select(f.company_id, func.max(f.fiscal_year).label("latest_fy"))
        .group_by(f.company_id)
        .subquery()
    )

    cols = (
        c.id.label("company_id"),
        c.ticker.label("ticker"),
        c.name.label("name"),
        c.industry_name.label("industry"),
        (m.fiscal_year if year else latest_m.c.latest_year).label("fiscal_year"),
        cast(m.cash_debt_ratio, Float).label("cash_debt_ratio"),
        m.growth_consistency.label("growth_consistency"),
        cast(m.rev_cagr_5y, Float).label("rev_cagr_5y"),
        cast(m.ni_cagr_5y, Float).label("ni_cagr_5y"),
        cast(m.fcf, Float).label("fcf"),
        cast(m.fcf_cagr_5y, Float).label("fcf_cagr_5y"),
        cast(p.pe_ttm, Float).label("pe_ttm"),
        cast(p.close_price, Float).label("price"),
        cast(f.shares_outstanding, Float).label("shares_outstanding"),
        (cast(p.close_price, Float) * cast(f.shares_outstanding, Float)).label("market_cap"),
    )

    stmt = select(*cols).select_from(c).where(c.is_tracked.is_(True))

    # ---- Filters ----
    filters = []

    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if ticker_list:
            filters.append(c.ticker.in_(ticker_list))

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
    if market_cap_min is not None:
        filters.append((p.close_price.isnot(None)) & (f.shares_outstanding.isnot(None)))
        filters.append((cast(p.close_price, Float) * cast(f.shares_outstanding, Float)) >= market_cap_min)

    # ---- Joins ----
    if year is None:
        stmt = (
            stmt.join(latest_m, latest_m.c.company_id == c.id)
            .join(m, (m.company_id == c.id) & (m.fiscal_year == latest_m.c.latest_year))
        )
    else:
        stmt = stmt.join(m, (m.company_id == c.id) & (m.fiscal_year == year))

    stmt = stmt.join(p, (p.company_id == c.id) & (p.fiscal_year == m.fiscal_year), isouter=True)
    stmt = (
        stmt.join(latest_f, latest_f.c.company_id == c.id, isouter=True)
        .join(f, (f.company_id == c.id) & (f.fiscal_year == latest_f.c.latest_fy), isouter=True)
    )

    if filters:
        stmt = stmt.where(and_(*filters))

    # ---- Count before pagination ----
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.execute(total_stmt).scalar() or 0

    # ---- Pagination ----
    stmt = stmt.order_by(
        p.pe_ttm.asc().nulls_last(),
        desc(m.cash_debt_ratio),
        c.ticker.asc(),
    ).limit(limit).offset(offset)

    rows = db.execute(stmt).mappings().all()
    return {"total_count": total_count, "items": [dict(r) for r in rows]}
