# app/api/valuation.py
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session


from app.core.db import get_db
from app.core.models import Company, FinancialAnnual, PriceAnnual



router = APIRouter(prefix="/valuation", tags=["valuation"])

def latest_financials_with_fcf(db: Session, company_id: int):
    sub = (
        select(func.max(FinancialAnnual.fiscal_year))
        .where(
            and_(
                FinancialAnnual.company_id == company_id,
                FinancialAnnual.cfo.isnot(None),
                FinancialAnnual.capex.isnot(None),
            )
        )
        .scalar_subquery()
    )
    return db.execute(
        select(FinancialAnnual).where(
            (FinancialAnnual.company_id == company_id) &
            (FinancialAnnual.fiscal_year == sub)
        )
    ).scalar_one_or_none()

# ---------------- helpers ----------------

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

def _latest_financials(db: Session, company_id: int):
    sub = (
        select(func.max(FinancialAnnual.fiscal_year))
        .where(FinancialAnnual.company_id == company_id)
        .scalar_subquery()
    )
    return db.execute(
        select(FinancialAnnual).where(
            (FinancialAnnual.company_id == company_id) &
            (FinancialAnnual.fiscal_year == sub)
        )
    ).scalar_one_or_none()

def _coalesce(*vals):
    for v in vals:
        if v is not None:
            return v
    return None

# ---------------- shared helper ----------------

def compute_quick_valuation(db: Session, company: Company,
                            years: int = 10,
                            discount_rate: float = 0.10,
                            start_growth: float = 0.05,
                            terminal_growth: float = 0.025):
    """Compute fair value and upside for one company (quick DCF).
       Returns dict with price, fvps, upside — or None if data missing.
    """
    from .valuation import latest_price_row, latest_financials_with_fcf, _coalesce

    pr = latest_price_row(db, company.id)
    price = float(pr.close_price) if (pr and pr.close_price is not None) else None

    fa = latest_financials_with_fcf(db, company.id)
    if not fa:
        return {"price": price, "fair_value_per_share": None, "upside_vs_price": None}

    ocf   = _coalesce(getattr(fa, "cfo", None), getattr(fa, "operating_cash_flow", None))
    capex = _coalesce(getattr(fa, "capex", None), getattr(fa, "capital_expenditures", None))
    if ocf is None or capex is None:
        return {"price": price, "fair_value_per_share": None, "upside_vs_price": None}

    base_fcf = float(ocf) - float(capex)
    cash   = float(fa.cash_and_sti or 0.0)
    debt   = float(fa.total_debt or 0.0)
    shares = float(fa.shares_outstanding or 0.0) or None

    # --- quick DCF as in /summary ---
    g = start_growth
    fade = (terminal_growth - start_growth) / max(years - 1, 1)
    fcf = base_fcf
    pv_total = 0.0
    for k in range(1, years + 1):
        if k == 1:
            fcf = base_fcf * (1 + g)
        else:
            g = g + fade
            fcf = fcf * (1 + g)
        df = 1.0 / ((1 + discount_rate) ** k)
        pv_total += fcf * df

    gT = terminal_growth
    terminal = fcf * (1 + gT) / (discount_rate - gT)
    pv_terminal = terminal / ((1 + discount_rate) ** years)

    enterprise_value = pv_total + pv_terminal
    equity_value = enterprise_value + cash - debt
    fvps = (equity_value / shares) if shares else None
    upside = (((fvps - price) / price) if (fvps is not None and price) else None)

    return {"price": price, "fair_value_per_share": fvps, "upside_vs_price": upside}


# -------------- /valuation/dcf --------------

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

    fa = _latest_financials(db, co.id)
    if not fa:
        raise HTTPException(400, "Missing latest financials row")

    # coalesce OCF & CapEx
    # app/api/valuation.py  (in both /dcf and /summary handlers where we build FCF)

    ocf   = _coalesce(getattr(fa, "cfo", None), getattr(fa, "operating_cash_flow", None))
    capex = _coalesce(getattr(fa, "capex", None), getattr(fa, "capital_expenditures", None))

    if ocf is None or capex is None:
        raise HTTPException(400, "Missing OCF/CapEx to compute FCF")

    base_year = int(fa.fiscal_year)
    base_fcf  = float(ocf) - float(capex)
    cash      = float(fa.cash_and_sti or 0.0)
    debt      = float(fa.total_debt or 0.0)
    shares    = float(fa.shares_outstanding or 0.0) or None

    p = latest_price_row(db, co.id)
    price = float(p.close_price) if (p and p.close_price is not None) else None

    # --- your existing single-horizon, linear fade DCF (same mechanics as before) ---
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

# -------------- /valuation/summary -----------

class ValSummaryOut(BaseModel):
    ticker: str
    price: Optional[float]
    fair_value_per_share: Optional[float]
    upside_vs_price: Optional[float]

@router.get("/summary", response_model=List[ValSummaryOut])
def valuation_summary(
    tickers: str = Query(..., description="Comma-separated tickers e.g. AAPL,MSFT,NVDA"),
    years: int = Query(10, ge=3, le=30),
    discount_rate: float = Query(0.10, gt=0),
    start_growth: float = Query(0.05),
    terminal_growth: float = Query(0.025),
    db: Session = Depends(get_db),
):
    want = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not want:
        return []

    companies = db.execute(
        select(Company).where(Company.ticker.in_(want), Company.is_tracked == True)
    ).scalars().all()

    out: List[ValSummaryOut] = []
    for co in companies:
        # ALWAYS fetch latest price first
        pr = latest_price_row(db, co.id)
        price = float(pr.close_price) if (pr and pr.close_price is not None) else None

        fa = latest_financials_with_fcf(db, co.id)
        if not fa:
            out.append(ValSummaryOut(
                ticker=co.ticker, price=price,
                fair_value_per_share=None, upside_vs_price=None
            ))
            continue

        # ✅ use getattr + _coalesce; table may not have these alt columns
        ocf   = _coalesce(getattr(fa, "cfo", None), getattr(fa, "operating_cash_flow", None))
        capex = _coalesce(getattr(fa, "capex", None), getattr(fa, "capital_expenditures", None))

        # ✅ keep price even if we can't compute FCF
        if ocf is None or capex is None:
            out.append(ValSummaryOut(
                ticker=co.ticker, price=price,
                fair_value_per_share=None, upside_vs_price=None
            ))
            continue

        # ✅ base FCF from coalesced values
        base_fcf = float(ocf) - float(capex)
        cash   = float(fa.cash_and_sti or 0.0)
        debt   = float(fa.total_debt or 0.0)
        shares = float(fa.shares_outstanding or 0.0) or None

        # --- quick DCF as before ---
        g = start_growth
        fade = (terminal_growth - start_growth) / max(years - 1, 1)
        fcf = base_fcf
        pv_total = 0.0
        for k in range(1, years + 1):
            if k == 1:
                fcf = base_fcf * (1 + g)
            else:
                g = g + fade
                fcf = fcf * (1 + g)
            df = 1.0 / ((1 + discount_rate) ** k)
            pv_total += fcf * df

        gT = terminal_growth
        terminal = fcf * (1 + gT) / (discount_rate - gT)
        pv_terminal = terminal / ((1 + discount_rate) ** years)

        enterprise_value = pv_total + pv_terminal
        equity_value = enterprise_value + cash - debt
        fvps = (equity_value / shares) if shares else None
        upside = (((fvps - price) / price) if (fvps is not None and price) else None)

        out.append(ValSummaryOut(
            ticker=co.ticker,
            price=price,
            fair_value_per_share=fvps,
            upside_vs_price=upside,
        ))

    return out
