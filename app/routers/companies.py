# app/routers/companies.py
from fastapi import APIRouter, Query, Depends, HTTPException, Path
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List

from app.core.db import get_db
from app.core.models import Company, FinancialAnnual, MetricsAnnual, PriceAnnual
from app.core.schemas import CompanyOut, CompanyProfileOut, ProfileSeries, ProfileSeriesPoint
from app.routers.valuation import compute_quick_valuation

router = APIRouter(prefix="/companies", tags=["companies"])

@router.get("")
def list_companies(
    industry: Optional[str] = Query(None),
    sic: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="search ticker or name (ilike)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    base = select(Company).where(Company.is_tracked.is_(True))
    if industry:
        base = base.where(Company.industry_name == industry)
    if sic:
        base = base.where(Company.sic == sic)
    if q:
        like = f"%{q}%"
        base = base.where(or_(Company.ticker.ilike(like), Company.name.ilike(like)))

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(Company.ticker.asc())
            .limit(page_size)
            .offset((page - 1) * page_size)
    ).all()

    return {
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "items": [
            {
                "id": co.id,
                "ticker": co.ticker,
                "name": co.name,
                "industry": co.industry_name,
                "sic": co.sic,
                "description": co.description,
            }
            for co in rows
        ],
    }


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: int = Path(..., description="Numeric company primary key (companies.id)"),
    db: Session = Depends(get_db),
):
    co = db.get(Company, company_id)
    if not co:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyOut.model_validate(co)


@router.get("/{identifier}/profile", response_model=CompanyProfileOut)
def get_company_profile(
    identifier: str = Path(..., description="Company id or ticker symbol"),
    db: Session = Depends(get_db),
):
    company = _resolve_company(db, identifier)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    financial_rows = db.scalars(
        select(FinancialAnnual)
        .where(FinancialAnnual.company_id == company.id)
        .order_by(FinancialAnnual.fiscal_year.asc())
    ).all()

    price_rows = db.scalars(
        select(PriceAnnual)
        .where(PriceAnnual.company_id == company.id)
        .order_by(PriceAnnual.fiscal_year.asc())
    ).all()

    latest_metrics = db.scalars(
        select(MetricsAnnual)
        .where(MetricsAnnual.company_id == company.id)
        .order_by(MetricsAnnual.fiscal_year.desc())
        .limit(1)
    ).first()

    latest_financial = financial_rows[-1] if financial_rows else None
    latest_price = price_rows[-1] if price_rows else None

    valuation = compute_quick_valuation(db, company) if company else {}
    price = _to_float((valuation or {}).get("price"))
    if price is None and latest_price is not None:
        price = _to_float(latest_price.close_price)

    shares = _to_float(getattr(latest_financial, "shares_outstanding", None))
    market_cap = price * shares if (price is not None and shares is not None) else None

    latest_year = None
    if latest_financial and getattr(latest_financial, "fiscal_year", None) is not None:
        latest_year = int(latest_financial.fiscal_year)
    elif latest_metrics and getattr(latest_metrics, "fiscal_year", None) is not None:
        latest_year = int(latest_metrics.fiscal_year)
    elif latest_price and getattr(latest_price, "fiscal_year", None) is not None:
        latest_year = int(latest_price.fiscal_year)

    valuation_block = {
        "price": price,
        "fair_value_per_share": _to_float((valuation or {}).get("fair_value_per_share")),
        "upside_vs_price": _to_float((valuation or {}).get("upside_vs_price")),
        "pe_ttm": _to_float(getattr(latest_price, "pe_ttm", None)),
    }

    total_debt = _to_float(getattr(latest_financial, "total_debt", None))
    equity_total = _to_float(getattr(latest_financial, "equity_total", None))

    financial_strength_block = {
        "cash_debt_ratio": _to_float(getattr(latest_metrics, "cash_debt_ratio", None)),
        "debt_to_equity": _ratio(total_debt, equity_total),
        "debt_ebitda": _to_float(getattr(latest_metrics, "debt_ebitda", None)),
        "interest_coverage": _to_float(getattr(latest_metrics, "interest_coverage", None)),
    }

    profitability_block = {
        "gross_margin": _to_float(getattr(latest_metrics, "gross_margin", None)),
        "op_margin": _to_float(getattr(latest_metrics, "op_margin", None)),
        "roe": _to_float(getattr(latest_metrics, "roe", None)),
        "roic": _to_float(getattr(latest_metrics, "roic", None)),
    }

    growth_block = {
        "rev_cagr_5y": _to_float(getattr(latest_metrics, "rev_cagr_5y", None)),
        "ni_cagr_5y": _to_float(getattr(latest_metrics, "ni_cagr_5y", None)),
        "rev_yoy": _to_float(getattr(latest_metrics, "rev_yoy", None)),
        "ni_yoy": _to_float(getattr(latest_metrics, "ni_yoy", None)),
        "fcf_cagr_5y": _to_float(getattr(latest_metrics, "fcf_cagr_5y", None)),
    }

    quality_block = {
        "piotroski_f": getattr(latest_metrics, "piotroski_f", None)
        if latest_metrics
        else None,
        "altman_z": _to_float(getattr(latest_metrics, "altman_z", None)),
        "growth_consistency": getattr(latest_metrics, "growth_consistency", None)
        if latest_metrics
        else None,
        "data_quality_score": _to_float(getattr(latest_metrics, "data_quality_score", None)),
    }

    balance_sheet_block = {
        "cash_and_sti": _to_float(getattr(latest_financial, "cash_and_sti", None)),
        "total_debt": total_debt,
        "assets_total": _to_float(getattr(latest_financial, "assets_total", None)),
        "equity_total": equity_total,
        "liabilities_current": _to_float(getattr(latest_financial, "liabilities_current", None)),
        "liabilities_longterm": _to_float(getattr(latest_financial, "liabilities_longterm", None)),
        "inventories": _to_float(getattr(latest_financial, "inventories", None)),
        "accounts_receivable": _to_float(getattr(latest_financial, "accounts_receivable", None)),
        "accounts_payable": _to_float(getattr(latest_financial, "accounts_payable", None)),
    }

    cash_flow_block = {
        "cfo": _to_float(getattr(latest_financial, "cfo", None)),
        "capex": _to_float(getattr(latest_financial, "capex", None)),
        "fcf": _to_float(
            getattr(latest_financial, "fcf", None)
            if latest_financial is not None
            else getattr(latest_metrics, "fcf", None)
        ),
        "dividends_paid": _to_float(getattr(latest_financial, "dividends_paid", None)),
        "share_repurchases": _to_float(getattr(latest_financial, "share_repurchases", None)),
    }

    series = ProfileSeries(
        price=_build_series(price_rows, "close_price"),
        revenue=_build_series(financial_rows, "revenue"),
        net_income=_build_series(financial_rows, "net_income"),
        cash=_build_series(financial_rows, "cash_and_sti"),
        debt=_build_series(financial_rows, "total_debt"),
        shares=_build_series(financial_rows, "shares_outstanding"),
    )

    return CompanyProfileOut(
        company=CompanyOut.model_validate(company),
        latest_fiscal_year=latest_year,
        price=price,
        market_cap=market_cap,
        valuation=valuation_block,
        financial_strength=financial_strength_block,
        profitability=profitability_block,
        growth=growth_block,
        quality=quality_block,
        balance_sheet=balance_sheet_block,
        cash_flow=cash_flow_block,
        series=series,
    )


def _to_float(value: Optional[object]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return numerator / denominator if denominator else None
    except ZeroDivisionError:
        return None


def _resolve_company(db: Session, identifier: str) -> Optional[Company]:
    identifier_trimmed = (identifier or "").strip()
    if not identifier_trimmed:
        return None

    company: Optional[Company] = None

    try:
        company_id = int(identifier_trimmed)
    except ValueError:
        company_id = None

    if company_id is not None:
        company = db.get(Company, company_id)
        if company:
            return company

    upper_ticker = identifier_trimmed.upper()
    company = db.execute(
        select(Company).where(func.upper(Company.ticker) == upper_ticker)
    ).scalar_one_or_none()
    return company


def _build_series(rows: List[object], attr: str) -> List[ProfileSeriesPoint]:
    out: List[ProfileSeriesPoint] = []
    for row in rows:
        fiscal_year = getattr(row, "fiscal_year", None)
        if fiscal_year is None:
            continue
        val = _to_float(getattr(row, attr, None))
        out.append(ProfileSeriesPoint(fiscal_year=int(fiscal_year), value=val))
    return out
