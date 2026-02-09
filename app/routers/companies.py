# app/routers/companies.py
from fastapi import APIRouter, Query, Depends, HTTPException, Path
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
import requests
import time

from app.core.db import get_db
from app.core.models import Company, FinancialAnnual, MetricsAnnual, PriceAnnual, CompanyRiskMetric
from app.core.schemas import (
    CompanyOut,
    CompanyProfileOut,
    ProfileSeries,
    ProfileSeriesPoint,
    ValuationHistoryPoint,
)
from app.routers.valuation import compute_quick_valuation
from app.core.config import settings

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


@router.get("/{identifier}", response_model=CompanyOut)
def get_company(
    identifier: str = Path(..., description="Company id or ticker symbol"),
    db: Session = Depends(get_db),
):
    co = _resolve_company(db, identifier)
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

    metrics_rows = db.scalars(
        select(MetricsAnnual)
        .where(MetricsAnnual.company_id == company.id)
        .order_by(MetricsAnnual.fiscal_year.asc())
    ).all()
    latest_metrics = metrics_rows[-1] if metrics_rows else None

    latest_financial = financial_rows[-1] if financial_rows else None
    latest_price = price_rows[-1] if price_rows else None

    valuation = compute_quick_valuation(db, company) if company else {}
    price = _to_float((valuation or {}).get("price"))

    live_price = _fetch_live_price(company.ticker) if company else None
    if live_price is not None:
        price = live_price
    elif price is None and latest_price is not None:
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

    eps_ttm = None
    shares = _to_float(getattr(latest_financial, "shares_outstanding", None))
    if shares and latest_financial and latest_financial.net_income not in (None,):
        eps_ttm = _ratio(_to_float(latest_financial.net_income), shares)

    valuation_block = {
        "price": price,
        "fair_value_per_share": _to_float((valuation or {}).get("fair_value_per_share")),
        "upside_vs_price": _to_float((valuation or {}).get("upside_vs_price")),
        "pe_ttm": _coalesce(
            _to_float(getattr(latest_price, "pe_ttm", None)),
            _ratio(price, eps_ttm) if price is not None and eps_ttm and eps_ttm != 0 else None,
        ),
    }

    total_debt = _to_float(getattr(latest_financial, "total_debt", None))
    equity_total = _to_float(getattr(latest_financial, "equity_total", None))

    cash_balance = _to_float(getattr(latest_financial, "cash_and_sti", None))
    operating_income_val = _to_float(getattr(latest_financial, "operating_income", None))
    interest_expense_val = _to_float(getattr(latest_financial, "interest_expense", None))

    financial_strength_block = {
        "cash_debt_ratio": _coalesce(
            _to_float(getattr(latest_metrics, "cash_debt_ratio", None)),
            _ratio(cash_balance, total_debt),
        ),
        "debt_to_equity": _ratio(total_debt, equity_total),
        "debt_ebitda": _to_float(getattr(latest_metrics, "debt_ebitda", None)),
        "interest_coverage": _coalesce(
            _to_float(getattr(latest_metrics, "interest_coverage", None)),
            _ratio(operating_income_val, interest_expense_val),
        ),
    }

    revenue_latest = _to_float(getattr(latest_financial, "revenue", None))
    gross_profit_latest = _to_float(getattr(latest_financial, "gross_profit", None))
    profitability_block = {
        "gross_margin": _coalesce(
            _to_float(getattr(latest_metrics, "gross_margin", None)),
            _ratio(gross_profit_latest, revenue_latest),
        ),
        "op_margin": _coalesce(
            _to_float(getattr(latest_metrics, "op_margin", None)),
            _ratio(operating_income_val, revenue_latest),
        ),
        "roe": _coalesce(
            _to_float(getattr(latest_metrics, "roe", None)),
            _ratio(_to_float(getattr(latest_financial, "net_income", None)), equity_total),
        ),
        "roic": _coalesce(
            _to_float(getattr(latest_metrics, "roic", None)),
            _compute_roic(latest_financial),
        ),
    }

    growth_block = {
        "rev_cagr_5y": _coalesce(
            _to_float(getattr(latest_metrics, "rev_cagr_5y", None)),
            _compute_cagr(financial_rows, "revenue", years=5),
        ),
        "ni_cagr_5y": _coalesce(
            _to_float(getattr(latest_metrics, "ni_cagr_5y", None)),
            _compute_cagr(financial_rows, "net_income", years=5),
        ),
        "rev_yoy": _coalesce(
            _to_float(getattr(latest_metrics, "rev_yoy", None)),
            _compute_yoy(financial_rows, "revenue"),
        ),
        "ni_yoy": _coalesce(
            _to_float(getattr(latest_metrics, "ni_yoy", None)),
            _compute_yoy(financial_rows, "net_income"),
        ),
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

    fcf_value = _to_float(
        getattr(latest_financial, "fcf", None)
        if latest_financial is not None
        else getattr(latest_metrics, "fcf", None)
    )
    cash_flow_block = {
        "cfo": _to_float(getattr(latest_financial, "cfo", None)),
        "capex": _to_float(getattr(latest_financial, "capex", None)),
        "fcf": _coalesce(
            fcf_value,
            _net_cash_flow(
                _to_float(getattr(latest_financial, "cfo", None)),
                _to_float(getattr(latest_financial, "capex", None)),
            ),
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

    risk_metric = db.scalars(
        select(CompanyRiskMetric).where(CompanyRiskMetric.company_id == company.id)
    ).first()
    risk_block = None
    if risk_metric:
        risk_block = {
            "alpha": _to_float(getattr(risk_metric, "alpha", None)),
            "alpha_annual": _to_float(getattr(risk_metric, "alpha_annual", None)),
            "alpha_annual_1y": _to_float(getattr(risk_metric, "alpha_annual_1y", None)),
            "alpha_annual_6m": _to_float(getattr(risk_metric, "alpha_annual_6m", None)),
            "alpha_annual_3m": _to_float(getattr(risk_metric, "alpha_annual_3m", None)),
            "beta": _to_float(getattr(risk_metric, "beta", None)),
            "benchmark": risk_metric.benchmark,
            "risk_free_rate": _to_float(getattr(risk_metric, "risk_free_rate", None)),
            "lookback_days": getattr(risk_metric, "lookback_days", None),
            "data_points": getattr(risk_metric, "data_points", None),
            "computed_at": risk_metric.computed_at.isoformat() if getattr(risk_metric, "computed_at", None) else None,
        }
    valuation_history = _build_pe_history(
        financial_rows,
        price_rows,
        metrics_rows,
        latest_financial,
        latest_metrics,
        price,
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
        risk_metrics=risk_block,
        valuation_history=valuation_history,
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


def _coalesce(*values: Optional[float]) -> Optional[float]:
    for v in values:
        if v is not None:
            return v
    return None


def _compute_yoy(rows: List[FinancialAnnual], attr: str) -> Optional[float]:
    if len(rows) < 2:
        return None

    latest = rows[-1]
    latest_year = getattr(latest, "fiscal_year", None)
    latest_val = _to_float(getattr(latest, attr, None))
    if latest_year is None or latest_val is None:
        return None

    comparison: Optional[FinancialAnnual] = None
    for row in reversed(rows[:-1]):
        year = getattr(row, "fiscal_year", None)
        if year is None:
            continue
        if latest_year - year >= 1:
            comparison = row
            break
    if comparison is None:
        comparison = rows[-2]

    prev_val = _to_float(getattr(comparison, attr, None))
    if prev_val in (None, 0):
        return None
    if (prev_val < 0) != (latest_val < 0):
        return None
    return latest_val / prev_val - 1


def _compute_cagr(rows: List[FinancialAnnual], attr: str, years: int = 5) -> Optional[float]:
    if len(rows) < 2:
        return None
    latest = rows[-1]
    latest_year = getattr(latest, "fiscal_year", None)
    latest_val = _to_float(getattr(latest, attr, None))
    if latest_year is None or latest_val is None or latest_val <= 0:
        return None

    base_row: Optional[FinancialAnnual] = None
    for row in rows[:-1]:
        year = getattr(row, "fiscal_year", None)
        if year is None:
            continue
        if latest_year - year >= years:
            base_row = row
    if base_row is None:
        base_row = rows[0]

    base_year = getattr(base_row, "fiscal_year", None)
    base_val = _to_float(getattr(base_row, attr, None))
    if base_year is None or base_val is None or base_val <= 0:
        return None

    year_span = latest_year - base_year
    if year_span <= 0:
        return None
    try:
        return (latest_val / base_val) ** (1 / year_span) - 1
    except (ZeroDivisionError, ValueError):
        return None


def _net_cash_flow(cfo: Optional[float], capex: Optional[float]) -> Optional[float]:
    if cfo is None or capex is None:
        return None
    return cfo - capex


def _compute_roic(financial: Optional[FinancialAnnual]) -> Optional[float]:
    if financial is None:
        return None
    net_income = _to_float(getattr(financial, "net_income", None))
    interest_expense = _to_float(getattr(financial, "interest_expense", None))
    tax_expense = _to_float(getattr(financial, "income_tax_expense", None))
    equity = _to_float(getattr(financial, "equity_total", None))
    debt = _to_float(getattr(financial, "total_debt", None))
    cash = _to_float(getattr(financial, "cash_and_sti", None))

    if net_income is None or equity is None or debt is None:
        return None

    # Approximate tax rate; guard against divide-by-zero
    tax_rate = None
    if net_income + (tax_expense or 0) != 0:
        tax_rate = _ratio(tax_expense, net_income + (tax_expense or 0))
    if tax_rate is None or tax_rate < 0:
        tax_rate = 0.21  # fallback

    nopat = net_income + (interest_expense or 0) * (1 - tax_rate)
    invested_capital = (equity or 0) + (debt or 0) - (cash or 0)
    if invested_capital == 0:
        return None
    return nopat / invested_capital


def _fetch_live_price(ticker: str) -> Optional[float]:
    key = settings.alpha_vantage_api_key
    if not key:
        return None
    # basic cache to avoid hammering
    cache_key = f"quote:{ticker.upper()}"
    now = time.time()
    if not hasattr(_fetch_live_price, "_cache"):
        _fetch_live_price._cache = {}
    cache = _fetch_live_price._cache
    if cache_key in cache:
        ts, val = cache[cache_key]
        if now - ts < 60:  # 1 minute TTL
            return val
    try:
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": ticker.upper(),
            "interval": "5min",
            "outputsize": "compact",
            "apikey": key,
        }
        resp = requests.get("https://www.alphavantage.co/query", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        series_key = "Time Series (5min)"
        series = data.get(series_key)
        if not series:
            return None
        latest_ts = sorted(series.keys())[-1]
        close = float(series[latest_ts]["4. close"])
        cache[cache_key] = (now, close)
        return close
    except Exception:
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


def _build_pe_history(
    financial_rows: List[FinancialAnnual],
    price_rows: List[PriceAnnual],
    metrics_rows: List[MetricsAnnual],
    latest_financial: Optional[FinancialAnnual],
    latest_metrics: Optional[MetricsAnnual],
    live_price: Optional[float],
    limit: int = 15,
) -> List[ValuationHistoryPoint]:
    price_map: Dict[int, Optional[float]] = {}
    for row in price_rows:
        if row.fiscal_year is None:
            continue
        price_map[int(row.fiscal_year)] = _to_float(getattr(row, "close_price", None))

    pe_map: Dict[int, Optional[float]] = {}
    for m in metrics_rows or []:
        if m.fiscal_year is None:
            continue
        pe_map[int(m.fiscal_year)] = _to_float(getattr(m, "pe_ttm", None))

    if not financial_rows:
        return []

    history: List[ValuationHistoryPoint] = []
    sorted_rows = sorted(
        (r for r in financial_rows if r.fiscal_year is not None),
        key=lambda r: r.fiscal_year,
    )[-limit:]

    for row in sorted_rows:
        fy = int(row.fiscal_year)
        price = price_map.get(fy)
        revenue = _to_float(getattr(row, "revenue", None))
        net_income = _to_float(getattr(row, "net_income", None))
        shares = _to_float(getattr(row, "shares_outstanding", None))
        eps = _ratio(net_income, shares) if net_income is not None and shares not in (None, 0) else None
        pe = _ratio(price, eps) if price is not None and eps not in (None, 0) else pe_map.get(fy)
        if pe is None and eps not in (None, 0) and pe_map.get(fy) is not None:
            pe = pe_map[fy]
        if price is None and pe is not None and eps not in (None, 0):
            price = eps * pe

        history.append(
            ValuationHistoryPoint(
                fiscal_year=fy,
                price=price,
                eps=eps,
                pe=pe,
                revenue=revenue,
                net_income=net_income,
                valuation_basis="FY" if pe is not None else None,
            )
        )
    history.sort(key=lambda r: r.fiscal_year)
    history_map = {row.fiscal_year: row for row in history}

    current_year = int(getattr(latest_financial, "fiscal_year", 0) or 0)
    if current_year and latest_financial:
        row = history_map.get(current_year)
        if not row:
            row = ValuationHistoryPoint(fiscal_year=current_year)
            history.append(row)
            history_map[current_year] = row

        eps_ttm = _to_float(getattr(latest_metrics, "ttm_eps", None)) if latest_metrics else None
        eps_fallback = row.eps
        if eps_fallback is None:
            eps_fallback = _ratio(
                _to_float(getattr(latest_financial, "net_income", None)),
                _to_float(getattr(latest_financial, "shares_outstanding", None)),
            )
        eps_current = eps_ttm if eps_ttm not in (None, 0) else eps_fallback
        price_current = live_price or row.price or price_map.get(current_year)
        if price_current is not None and eps_current not in (None, 0):
            row.price = price_current
            row.eps = eps_current
            row.pe = price_current / eps_current
            row.revenue = row.revenue or _to_float(getattr(latest_financial, "revenue", None))
            row.net_income = row.net_income or _to_float(getattr(latest_financial, "net_income", None))
            row.valuation_basis = "TTM" if eps_ttm not in (None, 0) else "FY (prev)"

    history.sort(key=lambda r: r.fiscal_year)
    return history[-limit:]
