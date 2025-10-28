from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import (
    Company,
    PharmaCompany,
    PharmaDrug,
    PharmaTrial,
)
from app.services.clinical_trials import fetch_studies, group_by_intervention
from app.services.pharma_refresh import refresh_company
from pydantic import BaseModel

router = APIRouter(prefix="/pharma", tags=["pharma"])

class ChatRequest(BaseModel):
    message: str


def _find_company_by_identifier(db: Session, identifier: str) -> PharmaCompany:
    ident = identifier.strip().upper()
    stmt = select(PharmaCompany).where(PharmaCompany.ticker == ident)
    pharma = db.execute(stmt).scalar_one_or_none()
    if pharma:
        return pharma

    try:
        company_id = int(ident)
    except ValueError:
        company_id = None

    if company_id is not None:
        stmt = select(PharmaCompany).where(PharmaCompany.company_id == company_id)
        pharma = db.execute(stmt).scalar_one_or_none()
        if pharma:
            return pharma

    stmt = select(Company).where(Company.ticker == ident)
    company = db.execute(stmt).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Lazily create pharma record so refresh endpoint can operate
    pharma = PharmaCompany(company_id=company.id, ticker=company.ticker, lead_sponsor=company.name)
    db.add(pharma)
    db.commit()
    db.refresh(pharma)
    return pharma


def _serialize_drug(drug: PharmaDrug) -> Dict[str, object]:
    return {
        "id": drug.id,
        "name": drug.name,
        "indication": drug.indication,
        "trials": [
            {
                "id": trial.id,
                "nct_id": trial.nct_id,
                "title": trial.title,
                "phase": trial.phase,
                "status": trial.status,
                "condition": trial.condition,
                "estimated_completion": trial.estimated_completion.isoformat() if trial.estimated_completion else None,
                "enrollment": trial.enrollment,
                "success_probability": float(trial.success_probability) if trial.success_probability is not None else None,
                "sponsor": trial.sponsor,
                "location": trial.location,
                "source_url": trial.source_url,
                "last_refreshed": trial.last_refreshed.isoformat() if trial.last_refreshed else None,
            }
            for trial in sorted(drug.trials, key=lambda t: (t.phase or "", t.status or ""))
        ],
    }


def _openai_client() -> Optional[OpenAI]:
    if not settings.pharma_openai_api_key:
        return None
    return OpenAI(api_key=settings.pharma_openai_api_key)


def _generate_analysis(company: Company, drugs: List[Dict[str, object]]) -> Optional[str]:
    client = _openai_client()
    if not client:
        return None

    drug_lines = []
    for drug in drugs:
        trials = drug.get("trials") or []
        if not trials:
            continue
        trial_lines = []
        for trial in trials:
            line = f"- {trial.get('phase') or 'Unknown Phase'} ({trial.get('status') or 'Status N/A'}), success {trial.get('success_probability') or 'N/A'}%"
            trial_lines.append(line)
        drug_lines.append(f"{drug['name']}: {', '.join(trial_lines)}")

    prompt = f"""
    Provide an investment-focused assessment for {company.name} ({company.ticker}).
    Focus on clinical pipeline strength, regulatory outlook, and commercial potential.
    Use the following pipeline context:

    {chr(10).join(drug_lines) if drug_lines else "No active trials listed."}

    Respond with two tight paragraphs and end with a clear BUY/HOLD/SELL recommendation.
    """

    try:
        completion = client.responses.create(
            model="gpt-5",
            input=prompt,
            reasoning={"effort": "low"},
            text={"verbosity": "medium"},
            max_output_tokens=600,
        )
        return completion.output_text
    except Exception:
        return None


@router.get("/companies")
def list_pharma_companies(
    search: Optional[str] = Query(None, description="Filter by ticker"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    drugs_subq = (
        select(PharmaDrug.pharma_company_id, func.count(PharmaDrug.id).label("drug_count"))
        .group_by(PharmaDrug.pharma_company_id)
        .subquery()
    )
    trials_subq = (
        select(
            PharmaDrug.pharma_company_id,
            func.count(PharmaTrial.id).label("trial_count"),
        )
        .join(PharmaTrial, PharmaTrial.pharma_drug_id == PharmaDrug.id)
        .group_by(PharmaDrug.pharma_company_id)
        .subquery()
    )

    stmt = (
        select(
            PharmaCompany,
            Company,
            func.coalesce(drugs_subq.c.drug_count, 0).label("drug_count"),
            func.coalesce(trials_subq.c.trial_count, 0).label("trial_count"),
        )
        .join(Company, Company.id == PharmaCompany.company_id)
        .join(drugs_subq, drugs_subq.c.pharma_company_id == PharmaCompany.id, isouter=True)
        .join(trials_subq, trials_subq.c.pharma_company_id == PharmaCompany.id, isouter=True)
    )

    if search:
        stmt = stmt.where(PharmaCompany.ticker.ilike(f"%{search.upper()}%"))

    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar()

    stmt = stmt.order_by(PharmaCompany.ticker.asc()).limit(limit).offset(offset)
    rows = db.execute(stmt).all()

    items = []
    for pharma, company, drug_count, trial_count in rows:
        items.append(
            {
                "ticker": pharma.ticker,
                "company_id": pharma.company_id,
                "name": company.name,
                "industry": company.industry_name,
                "lead_sponsor": pharma.lead_sponsor,
                "last_refreshed": pharma.last_refreshed.isoformat() if pharma.last_refreshed else None,
                "drug_count": drug_count,
                "trial_count": trial_count,
            }
        )

    return {
        "total": total or 0,
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{identifier}")
def get_pharma_company(
    identifier: str = Path(..., description="Ticker symbol or pharma company identifier"),
    force_live: bool = Query(False, description="Fetch fresh data from ClinicalTrials.gov without persisting"),
    db: Session = Depends(get_db),
):
    pharma = _find_company_by_identifier(db, identifier)
    company = pharma.company
    if not company:
        raise HTTPException(status_code=404, detail="Linked company missing")

    serialized_drugs = [_serialize_drug(drug) for drug in pharma.drugs]
    live_trials = None
    if force_live or not serialized_drugs:
        try:
            studies, _ = fetch_studies(lead=pharma.lead_sponsor or company.name, page_size=100, max_pages=2)
            grouped = group_by_intervention(studies)
            live_drugs = []
            for drug_name, records in grouped.items():
                trials = []
                for record in records:
                    trials.append(
                        {
                            "nct_id": record.get("nct_id"),
                            "title": record.get("title"),
                            "phase": record.get("phase"),
                            "status": record.get("status"),
                            "condition": ", ".join(record.get("conditions") or []),
                            "estimated_completion": record.get("estimated_completion").isoformat()
                            if isinstance(record.get("estimated_completion"), datetime)
                            else None,
                            "enrollment": record.get("enrollment"),
                            "success_probability": record.get("success_probability"),
                            "sponsor": record.get("lead_sponsor"),
                            "location": record.get("location"),
                            "source_url": record.get("source_url"),
                        }
                    )
                live_drugs.append(
                    {
                        "name": drug_name,
                        "indication": ", ".join(records[0].get("conditions") or []),
                        "trials": trials,
                    }
                )
            live_trials = live_drugs
        except Exception:
            live_trials = None

    analysis = _generate_analysis(company, live_trials or serialized_drugs) if (live_trials or serialized_drugs) else None

    return {
        "company": {
            "id": company.id,
            "ticker": company.ticker,
            "name": company.name,
            "industry": company.industry_name,
            "lead_sponsor": pharma.lead_sponsor,
            "last_refreshed": pharma.last_refreshed.isoformat() if pharma.last_refreshed else None,
        },
        "drugs": serialized_drugs,
        "live_drugs": live_trials,
        "analysis": analysis,
    }


@router.post("/{identifier}/refresh")
def refresh_pharma_company(
    identifier: str,
    lead: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    pharma = _find_company_by_identifier(db, identifier)
    company = pharma.company
    if not company:
        raise HTTPException(status_code=404, detail="Linked company missing")

    try:
        count = refresh_company(db, company, lead=lead, status=status)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refresh trials: {exc}") from exc

    return {"ticker": company.ticker, "refreshed_trials": count}


@router.post("/chat")
def pharma_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    client = _openai_client()
    if not client:
        raise HTTPException(status_code=503, detail="Pharma chat not configured")

    # Build compact dataset context
    stmt = (
        select(
            PharmaCompany.ticker,
            PharmaDrug.name,
            PharmaTrial.phase,
            PharmaTrial.status,
            PharmaTrial.success_probability,
        )
        .join(PharmaDrug, PharmaDrug.pharma_company_id == PharmaCompany.id)
        .join(PharmaTrial, PharmaTrial.pharma_drug_id == PharmaDrug.id)
    )
    rows = db.execute(stmt).all()
    context_lines = [
        f"{ticker}: {drug} - {phase or 'N/A'} ({status or 'unknown'}), success {success_probability or 'n/a'}%"
        for ticker, drug, phase, status, success_probability in rows
    ]

    prompt = f"""
    You are a biotech investment copilot. Answer the user's question using the following pipeline context:

    {chr(10).join(context_lines) if context_lines else 'No stored trial data yet.'}

    User question: {payload.message}
    """

    try:
        completion = client.responses.create(
            model="gpt-5",
            input=prompt,
            reasoning={"effort": "low"},
            text={"verbosity": "medium"},
            max_output_tokens=600,
        )
        return {"response": completion.output_text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {exc}") from exc
