from __future__ import annotations

import json
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from openai import OpenAI

from app.core.config import settings
from app.core.db import get_db
from app.core.models import Company, FinancialAnnual, FinancialQuarterly, ModelingAssumption, ModelingKPI
from app.core.schemas import (
    CompanyOut,
    FinancialQuarterlyOut,
    ModelingAssumptionIn,
    ModelingAssumptionOut,
    ModelingChatRequest,
    ModelingChatResponse,
    ModelingKPIIn,
    ModelingKPIOut,
    ModelingRunRequest,
    ModelingRunResponse,
    ModelingScenarioOut,
)
from app.modeling.forecaster import Assumptions, KPI, generate_forecast, rollup_annual
from app.services.llm_usage import record_openai_usage


router = APIRouter(prefix="/modeling", tags=["modeling"])


DEFAULT_SCENARIOS = {
    "base": {
        "revenue_cagr_start": 0.18,
        "revenue_cagr_floor": 0.04,
        "revenue_decay_quarters": 12,
        "gross_margin_target": 0.52,
        "gross_margin_glide_quarters": 12,
        "rnd_pct": 0.12,
        "sm_pct": 0.14,
        "ga_pct": 0.06,
        "tax_rate": 0.18,
        "interest_pct_revenue": 0.005,
        "dilution_pct_annual": 0.015,
        "seasonality_mode": "auto",
        "driver_blend_start_weight": 0.3,
        "driver_blend_end_weight": 0.7,
        "driver_blend_ramp_quarters": 6,
    },
    "bull": {
        "revenue_cagr_start": 0.25,
        "revenue_cagr_floor": 0.06,
        "revenue_decay_quarters": 16,
        "gross_margin_target": 0.56,
        "gross_margin_glide_quarters": 12,
        "rnd_pct": 0.11,
        "sm_pct": 0.12,
        "ga_pct": 0.05,
        "tax_rate": 0.16,
        "interest_pct_revenue": 0.003,
        "dilution_pct_annual": 0.01,
        "seasonality_mode": "auto",
        "driver_blend_start_weight": 0.3,
        "driver_blend_end_weight": 0.7,
        "driver_blend_ramp_quarters": 6,
    },
    "bear": {
        "revenue_cagr_start": 0.1,
        "revenue_cagr_floor": 0.02,
        "revenue_decay_quarters": 8,
        "gross_margin_target": 0.48,
        "gross_margin_glide_quarters": 8,
        "rnd_pct": 0.13,
        "sm_pct": 0.16,
        "ga_pct": 0.07,
        "tax_rate": 0.2,
        "interest_pct_revenue": 0.008,
        "dilution_pct_annual": 0.02,
        "seasonality_mode": "auto",
        "driver_blend_start_weight": 0.3,
        "driver_blend_end_weight": 0.7,
        "driver_blend_ramp_quarters": 6,
    },
}


def _openai_client() -> OpenAI:
    key = settings.modeling_openai_api_key or settings.pharma_openai_api_key
    if not key:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    return OpenAI(api_key=key)


def _assumption_from_payload(payload: ModelingAssumptionIn) -> Assumptions:
    data = DEFAULT_SCENARIOS.get(payload.scenario, DEFAULT_SCENARIOS["base"])
    merged = {**data, **payload.model_dump(exclude={"scenario"}, exclude_none=True)}
    return Assumptions(scenario=payload.scenario, **merged)


def _assumption_out_from_assumptions(assumption: Assumptions) -> ModelingAssumptionOut:
    return ModelingAssumptionOut(
        scenario=assumption.scenario,
        revenue_cagr_start=assumption.revenue_cagr_start,
        revenue_cagr_floor=assumption.revenue_cagr_floor,
        revenue_decay_quarters=assumption.revenue_decay_quarters,
        gross_margin_target=assumption.gross_margin_target,
        gross_margin_glide_quarters=assumption.gross_margin_glide_quarters,
        rnd_pct=assumption.rnd_pct,
        sm_pct=assumption.sm_pct,
        ga_pct=assumption.ga_pct,
        tax_rate=assumption.tax_rate,
        interest_pct_revenue=assumption.interest_pct_revenue,
        dilution_pct_annual=assumption.dilution_pct_annual,
        seasonality_mode=assumption.seasonality_mode,
        driver_blend_start_weight=assumption.driver_blend_start_weight,
        driver_blend_end_weight=assumption.driver_blend_end_weight,
        driver_blend_ramp_quarters=assumption.driver_blend_ramp_quarters,
    )


def _assumption_from_db(row: ModelingAssumption) -> ModelingAssumptionOut:
    return ModelingAssumptionOut.model_validate(row)


def _load_assumptions(db: Session, company_id: int) -> List[ModelingAssumptionOut]:
    rows = db.execute(
        select(ModelingAssumption).where(ModelingAssumption.company_id == company_id)
    ).scalars()
    stored = {row.scenario: row for row in rows}
    results: List[ModelingAssumptionOut] = []
    for scenario, defaults in DEFAULT_SCENARIOS.items():
        if scenario in stored:
            results.append(_assumption_from_db(stored[scenario]))
        else:
            results.append(ModelingAssumptionOut(scenario=scenario, **defaults))
    return results


def _annual_to_quarters(annual_rows: List[FinancialAnnual]) -> List[Dict[str, float]]:
    quarters: List[Dict[str, float]] = []
    for row in annual_rows:
        if row.revenue is None:
            continue
        revenue = float(row.revenue) / 4
        gross_profit = float(row.gross_profit) / 4 if row.gross_profit is not None else None
        operating_income = float(row.operating_income) / 4 if row.operating_income is not None else None
        net_income = float(row.net_income) / 4 if row.net_income is not None else None
        shares = float(row.shares_outstanding) if row.shares_outstanding is not None else None
        for period in ("Q1", "Q2", "Q3", "Q4"):
            quarters.append(
                {
                    "fiscal_year": row.fiscal_year,
                    "fiscal_period": period,
                    "revenue": revenue,
                    "gross_profit": gross_profit,
                    "operating_income": operating_income,
                    "net_income": net_income,
                    "shares_outstanding": shares,
                }
            )
    return quarters


@router.get("/{company_id}")
def get_modeling_data(company_id: int, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    assumptions = _load_assumptions(db, company_id)
    kpis = db.execute(
        select(ModelingKPI)
        .where(ModelingKPI.company_id == company_id)
        .order_by(ModelingKPI.fiscal_year, ModelingKPI.fiscal_period)
    ).scalars().all()
    financials = db.execute(
        select(FinancialQuarterly)
        .where(FinancialQuarterly.company_id == company_id)
        .order_by(FinancialQuarterly.fiscal_year, FinancialQuarterly.fiscal_period)
    ).scalars()
    financials_list = list(financials)
    if not financials_list:
        annual_rows = db.execute(
            select(FinancialAnnual)
            .where(FinancialAnnual.company_id == company_id)
            .order_by(FinancialAnnual.fiscal_year)
        ).scalars().all()
        fallback = _annual_to_quarters(annual_rows)
        return {
            "company": CompanyOut.model_validate(company),
            "fiscal_year_end_month": company.fiscal_year_end_month,
            "assumptions": assumptions,
            "kpis": [ModelingKPIOut.model_validate(k) for k in kpis],
            "financials_quarterly": fallback,
        }

    return {
        "company": CompanyOut.model_validate(company),
        "fiscal_year_end_month": company.fiscal_year_end_month,
        "assumptions": assumptions,
        "kpis": [ModelingKPIOut.model_validate(k) for k in kpis],
        "financials_quarterly": [FinancialQuarterlyOut.model_validate(f) for f in financials_list],
    }


@router.put("/{company_id}/assumptions")
def upsert_assumptions(
    company_id: int, payload: List[ModelingAssumptionIn], db: Session = Depends(get_db)
):
    for item in payload:
        existing = db.execute(
            select(ModelingAssumption)
            .where(
                ModelingAssumption.company_id == company_id,
                ModelingAssumption.scenario == item.scenario,
            )
        ).scalar_one_or_none()
        data = item.model_dump(exclude_none=True)
        if existing:
            for key, value in data.items():
                if key != "scenario":
                    setattr(existing, key, value)
        else:
            db.add(ModelingAssumption(company_id=company_id, **data))
    db.commit()
    return {"status": "ok"}


@router.put("/{company_id}/kpis")
def upsert_kpis(company_id: int, payload: List[ModelingKPIIn], db: Session = Depends(get_db)):
    for item in payload:
        existing = db.execute(
            select(ModelingKPI).where(
                ModelingKPI.company_id == company_id,
                ModelingKPI.fiscal_year == item.fiscal_year,
                ModelingKPI.fiscal_period == item.fiscal_period,
            )
        ).scalar_one_or_none()
        data = item.model_dump(exclude_none=True)
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
        else:
            db.add(ModelingKPI(company_id=company_id, **data))
    db.commit()
    return {"status": "ok"}


@router.post("/{company_id}/run", response_model=ModelingRunResponse)
def run_model(company_id: int, payload: ModelingRunRequest, db: Session = Depends(get_db)):
    financials = db.execute(
        select(FinancialQuarterly)
        .where(FinancialQuarterly.company_id == company_id)
        .order_by(FinancialQuarterly.fiscal_year, FinancialQuarterly.fiscal_period)
    ).scalars()
    financials_list = list(financials)
    if not financials_list:
        annual_rows = db.execute(
            select(FinancialAnnual)
            .where(FinancialAnnual.company_id == company_id)
            .order_by(FinancialAnnual.fiscal_year)
        ).scalars().all()
        historical_quarters = _annual_to_quarters(annual_rows)
    else:
        historical_quarters = [
            {
                "fiscal_year": f.fiscal_year,
                "fiscal_period": f.fiscal_period,
                "revenue": float(f.revenue) if f.revenue is not None else None,
                "cost_of_revenue": float(f.cost_of_revenue) if f.cost_of_revenue is not None else None,
                "gross_profit": float(f.gross_profit) if f.gross_profit is not None else None,
                "research_and_development": float(f.research_and_development) if f.research_and_development is not None else None,
                "sales_and_marketing": float(f.sales_and_marketing) if f.sales_and_marketing is not None else None,
                "general_and_administrative": float(f.general_and_administrative) if f.general_and_administrative is not None else None,
                "operating_income": float(f.operating_income) if f.operating_income is not None else None,
                "interest_expense": float(f.interest_expense) if f.interest_expense is not None else None,
                "income_tax_expense": float(f.income_tax_expense) if f.income_tax_expense is not None else None,
                "net_income": float(f.net_income) if f.net_income is not None else None,
                "shares_outstanding": float(f.shares_outstanding) if f.shares_outstanding is not None else None,
            }
            for f in financials_list
        ]

    kpi_rows = [
        KPI(
            fiscal_year=k.fiscal_year,
            fiscal_period=k.fiscal_period,
            mau=float(k.mau) if k.mau is not None else None,
            dau=float(k.dau) if k.dau is not None else None,
            paid_subs=float(k.paid_subs) if k.paid_subs is not None else None,
            paid_conversion_pct=float(k.paid_conversion_pct) if k.paid_conversion_pct is not None else None,
            arpu=float(k.arpu) if k.arpu is not None else None,
            churn_pct=float(k.churn_pct) if k.churn_pct is not None else None,
        )
        for k in payload.kpis
    ]

    horizon = max(4, min(payload.horizon_quarters, 80))
    scenarios: List[ModelingScenarioOut] = []
    assumptions_payload = payload.assumptions or _load_assumptions(db, company_id)
    for item in assumptions_payload:
        if isinstance(item, ModelingAssumptionOut):
            item = ModelingAssumptionIn(**item.model_dump())
        assumption = _assumption_from_payload(item)
        quarters = generate_forecast(assumption, historical_quarters, kpi_rows, horizon)
        annual = rollup_annual(quarters)
        scenarios.append(
            ModelingScenarioOut(
                name=assumption.scenario,
                assumptions=_assumption_out_from_assumptions(assumption),
                quarterly=quarters,
                annual=annual,
            )
        )

    return ModelingRunResponse(scenarios=scenarios)


@router.post("/{company_id}/chat", response_model=ModelingChatResponse)
def chat_with_modeling_ai(company_id: int, payload: ModelingChatRequest, db: Session = Depends(get_db)):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    client = _openai_client()
    system = (
        "You are a financial modeling assistant. "
        "Return JSON only with keys: reply, proposed_edits. "
        "proposed_edits is a list of objects with path, old, new, reason. "
        "Use decimal fractions for percent values."
    )
    prompt = {
        "company": {"ticker": company.ticker, "name": company.name, "industry": company.industry_name},
        "message": payload.message,
        "assumptions": [a.model_dump() for a in payload.assumptions],
        "kpis": [k.model_dump() for k in payload.kpis],
        "history": payload.history,
    }

    response = None
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(prompt)},
            ],
            temperature=0.2,
        )
    except Exception as exc:
        record_openai_usage(
            endpoint=f"/modeling/{company_id}/chat",
            api="chat_completions",
            model="gpt-4.1",
            response=None,
            success=False,
            error=type(exc).__name__,
            metadata={"router": "modeling"},
        )
        raise
    else:
        record_openai_usage(
            endpoint=f"/modeling/{company_id}/chat",
            api="chat_completions",
            model="gpt-4.1",
            response=response,
            success=True,
            metadata={"router": "modeling"},
        )

    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"reply": raw, "proposed_edits": []}

    proposed = data.get("proposed_edits", [])
    if not isinstance(proposed, list):
        proposed = []
    cleaned = []
    for item in proposed:
        if not isinstance(item, dict):
            continue
        cleaned.append({
            "path": str(item.get("path")) if item.get("path") is not None else None,
            "old": str(item.get("old")) if item.get("old") is not None else None,
            "new": str(item.get("new")) if item.get("new") is not None else None,
            "reason": str(item.get("reason")) if item.get("reason") is not None else None,
        })

    return ModelingChatResponse(
        reply=data.get("reply", ""),
        proposed_edits=cleaned,
    )
