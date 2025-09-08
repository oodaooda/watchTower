# app/routers/screen.py
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, Float, select, func, and_, or_, asc, desc
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Company, MetricsAnnual, PriceAnnual, FinancialAnnual

router = APIRouter(prefix="/screen", tags=["screen"])


@router.get("")
def run_screen(
    q: Optional[str] = Query(None, description="Search ticker or company name (ILIKE)"),
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
    include_untracked: bool = Query(False, description="Include untracked companies as well"),
    # NEW: global sort across the full result set
    sort_key: Optional[str] = Query(
        None,
        description=(
            "Sort key (whitelist): "
            "ticker,name,industry,fiscal_year,pe_ttm,cash_debt_ratio,"
            "growth_consistency,rev_cagr_5y,ni_cagr_5y,fcf_cagr_5y,price"
        ),
    ),
    sort_dir: str = Query("asc", regex="^(asc|desc)$", description="Sort direction: asc or desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns paginated screener results with optional server-side sort.

    Response:
    {
        "total_count": int,
        "items": [ {row}, ... ]
    }
    """

    # --- Aliases
    c, m, p, f = Company, MetricsAnnual, PriceAnnual, FinancialAnnual

    # --- Params / aliases (back-compat)
    cash_min = cash_debt_min if cash_debt_min is not None else cash_debt_gte
    growth_min = (
        growth_consistency_min
        if growth_consistency_min is not None
        else growth_consistency_gte
    )

    # --- Subqueries for latest rows
    if year is None:
        latest_m = (
            select(m.company_id, func.max(m.fiscal_year).label("latest_year"))
            .group_by(m.company_id)
            .subquery()
        )

    latest_f = (
        select(f.company_id, func.max(f.fiscal_year).label("latest_fy"))
        .group_by(f.company_id)
        .subquery()
    )

    latest_p = (
        select(p.company_id, func.max(p.fiscal_year).label("fy_price"))
        .group_by(p.company_id)
        .subquery()
    )

    # --- Columns
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

    # --- Base FROM / WHERE
    stmt = select(*cols).select_from(c)
    if not include_untracked:
        stmt = stmt.where(c.is_tracked.is_(True))

    # --- Joins
    if year is None:
        stmt = (
            stmt.join(latest_m, latest_m.c.company_id == c.id)
            .join(m, (m.company_id == c.id) & (m.fiscal_year == latest_m.c.latest_year))
        )
        fy_sort_col = latest_m.c.latest_year
    else:
        stmt = stmt.join(m, (m.company_id == c.id) & (m.fiscal_year == year))
        fy_sort_col = m.fiscal_year

    stmt = (
        stmt.join(latest_p, latest_p.c.company_id == c.id, isouter=True)
        .join(p, (p.company_id == c.id) & (p.fiscal_year == latest_p.c.fy_price), isouter=True)
    )

    stmt = (
        stmt.join(latest_f, latest_f.c.company_id == c.id, isouter=True)
        .join(f, (f.company_id == c.id) & (f.fiscal_year == latest_f.c.latest_fy), isouter=True)
    )

    # --- Filters
    filters = []

    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(c.ticker.ilike(like), c.name.ilike(like)))

    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if ticker_list:
            filters.append(c.ticker.in_(ticker_list))

    if industry:
        # exact match by industry_name or by SIC
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

    if filters:
        stmt = stmt.where(and_(*filters))

    # --- Count before pagination
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = db.execute(total_stmt).scalar() or 0

    # --- Sorting (server-side, across full result set)
    # Build whitelist AFTER joins so we can use the correct fiscal_year column
    SORT_MAP = {
        "ticker": c.ticker,
        "name": c.name,
        "industry": c.industry_name,
        "fiscal_year": fy_sort_col,           # dynamic (pinned year or latest)
        "pe_ttm": p.pe_ttm,
        "cash_debt_ratio": m.cash_debt_ratio,
        "growth_consistency": m.growth_consistency,
        "rev_cagr_5y": m.rev_cagr_5y,
        "ni_cagr_5y": m.ni_cagr_5y,
        "fcf_cagr_5y": m.fcf_cagr_5y,
        "price": p.close_price,
        # NOTE: fair_value_per_share / upside_vs_price are client-merged; not sortable here
    }

    order_cols = []
    col = SORT_MAP.get((sort_key or "").strip()) if sort_key else None
    if col is not None:
        # NULLS LAST so incomplete data doesn't float to the top
        order_cols.append(col.asc().nulls_last() if sort_dir == "asc" else col.desc().nulls_last())
        # Secondary stable key
        order_cols.append(c.ticker.asc())
    else:
        # Default order (previous behavior)
        order_cols.extend([
            p.pe_ttm.asc().nulls_last(),
            desc(m.cash_debt_ratio),
            c.ticker.asc(),
        ])

    stmt = stmt.order_by(*order_cols).limit(limit).offset(offset)

    # --- Execute
    rows = db.execute(stmt).mappings().all()
    return {"total_count": total_count, "items": [dict(r) for r in rows]}
