# app/api/valuation.py
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Company, FinancialAnnual, PriceAnnual

router = APIRouter(prefix="/valuation", tags=["valuation"])

def latest_price_row(db: Session, company_id: int):
    sub = (
        select(func.max(PriceAnnual.fiscal_year))
        .where(PriceAnnual.company_id == company_id)
        .scalar_subquery()
    )
    return db.execute(
        select(PriceAnnual).where(
            (PriceAnnual.company_id == company_id) & (PriceAnnual.fiscal_year == sub)
        )
    ).scalar_one_or_none()

@router.get("/dcf")
def dcf_endpoint(
    ticker: str = Query(...),
    years: int = Query(10, ge=3, le=30),
    discount_rate: float = Query(0.10, gt=0),
    start_growth: float = Query(0.05),
    terminal_growth: float = Query(0.025),
    db: Session = Depends(get_db),
):
    co = db.execute(
        select(Company).where(Company.ticker == ticker.upper(), Company.is_tracked == True)
    ).scalar_one_or_none()
    if not co:
        raise HTTPException(404, f"Unknown ticker: {ticker}")

    # latest base year from metrics/fundamentals (you already compute FCF in metrics_annual)
    m_sub = select(func.max(FinancialAnnual.fiscal_year)).where(
        FinancialAnnual.company_id == co.id
    ).scalar_subquery()

    m_latest = db.execute(
        select(FinancialAnnual).where(
            (FinancialAnnual.company_id == co.id) & (FinancialAnnual.fiscal_year == m_sub)
        )
    ).scalar_one_or_none()
    if not m_latest or m_latest.cfo is None or m_latest.capex is None:
        raise HTTPException(400, "Missing OCF/CapEx to compute FCF")

    base_year = int(m_latest.fiscal_year)
    base_fcf = float((m_latest.cfo or 0) - (m_latest.capex or 0))
    cash = float(m_latest.cash_and_sti or 0.0)
    debt = float(m_latest.total_debt or 0.0)
    shares = float(m_latest.shares_outstanding or 0.0) or None

    # latest price (if any)
    p = latest_price_row(db, co.id)
    price = float(p.close_price) if (p and p.close_price is not None) else None

    # --- simple DCF chain (same as you already implemented) ---
    years_arr = list(range(1, years + 1))
    g = start_growth
    fade = (terminal_growth - start_growth) / max(years - 1, 1)

    projections = []
    fcf = base_fcf
    pv = 0.0
    for k in years_arr:
        if k == 1:
            fcf = base_fcf * (1 + g)
        else:
            g = g + fade
            fcf = projections[-1]["fcf"] * (1 + g)

        df = 1.0 / ((1 + discount_rate) ** k)
        pv_fcf = fcf * df
        pv += pv_fcf
        projections.append(
            {"year": base_year + k, "fcf": fcf, "growth": g, "discount_factor": df, "pv_fcf": pv_fcf}
        )

    # Terminal value (Gordon)
    gT = terminal_growth
    tv = projections[-1]["fcf"] * (1 + gT) / (discount_rate - gT)
    tv_pv = tv / ((1 + discount_rate) ** years)

    enterprise_value = pv + tv_pv
    equity_value = enterprise_value + cash - debt
    fair_value_per_share = (equity_value / shares) if shares else None
    upside_vs_price = (
        ((fair_value_per_share - price) / price) if (fair_value_per_share and price and price > 0) else None
    )

    return {
        "ticker": co.ticker,
        "base_year": base_year,
        "inputs": {
            "years": years,
            "discount_rate": discount_rate,
            "start_growth": start_growth,
            "terminal_growth": terminal_growth,
        },
        "balance_sheet": {
            "cash_and_sti": cash,
            "total_debt": debt,
            "shares_outstanding": shares,
        },
        "price": price,
        "base_fcf": base_fcf,
        "projections": projections,
        "terminal_value": tv,
        "terminal_value_pv": tv_pv,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "fair_value_per_share": fair_value_per_share,
        "upside_vs_price": upside_vs_price,
    }
