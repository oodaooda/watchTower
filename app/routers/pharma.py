from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.db import get_db
from app.core.models import (
    Company,
    PharmaCompany,
    PharmaDrug,
    PharmaTrial,
    PharmaDrugMetadata,
)
from app.services.clinical_trials import (
    fetch_studies,
    group_by_intervention,
    status_category as classify_status,
)
from app.services.pharma_refresh import refresh_company
from app.services.llm_usage import record_openai_usage
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


def _friendly_status(status: Optional[str]) -> Optional[str]:
    if not status:
        return None
    return status.replace("_", " ").title()


def _outcome_text(status: Optional[str], why_stopped: Optional[str], has_results: Optional[bool]) -> Optional[str]:
    if not status:
        return why_stopped
    normalized = status.upper()
    if normalized.startswith("COMPLETED"):
        if has_results:
            return "Completed (results posted)"
        return why_stopped or "Completed"
    if normalized.startswith("APPROVED"):
        return "Approved for marketing"
    if normalized.startswith("TERMINATED"):
        return why_stopped or "Terminated"
    if normalized.startswith("WITHDRAWN"):
        return why_stopped or "Withdrawn"
    if why_stopped:
        return why_stopped
    return None


PHASE_PRIORITY: Dict[str, int] = {
    "PRECLINICAL": 1,
    "EARLY PHASE 1": 2,
    "PHASE 1": 3,
    "PHASE 1/PHASE 2": 4,
    "PHASE 2": 5,
    "PHASE 2/PHASE 3": 6,
    "PHASE 3": 7,
    "PHASE 3/PHASE 4": 8,
    "PHASE 4": 9,
    "FDA REVIEW": 10,
    "APPROVED": 11,
    "APPROVED FOR MARKETING": 12,
    "COMMERCIAL": 13,
}


def _phase_rank(phase: Optional[str]) -> int:
    if not phase:
        return 0
    key = phase.strip().upper()
    if key in PHASE_PRIORITY:
        return PHASE_PRIORITY[key]
    key = key.replace(" ", "")
    return PHASE_PRIORITY.get(key, 0)


def _payload_date(value: Optional[object]) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.min
    return datetime.min


def _payload_sort_tuple(payload: Dict[str, object]) -> Tuple[int, datetime, float]:
    phase_rank = int(payload.get("phase_rank") or 0)
    verified_date = _payload_date(payload.get("status_last_verified"))
    probability = payload.get("success_probability")
    probability_value = float(probability) if isinstance(probability, (int, float)) else 0.0
    return (phase_rank, verified_date, probability_value)


def _clean_payload(payload: Dict[str, object]) -> Dict[str, object]:
    clean = dict(payload)
    clean.pop("phase_rank", None)
    clean.pop("status_raw", None)
    return clean


def _serialize_sales(metadata: Optional[PharmaDrugMetadata]) -> Dict[str, List[Dict[str, object]]]:
    if not metadata or not metadata.sales:
        return {"annual": [], "quarterly": []}

    annual: List[Dict[str, object]] = []
    quarterly: List[Dict[str, object]] = []
    for sale in metadata.sales:
        payload = {
            "year": sale.period_year,
            "quarter": sale.period_quarter,
            "revenue": float(sale.revenue) if sale.revenue is not None else None,
            "currency": sale.currency,
            "source": sale.source,
        }
        if sale.period_type.lower() == "annual":
            annual.append(payload)
        else:
            quarterly.append(payload)

    annual.sort(key=lambda item: item.get("year") or 0, reverse=True)
    quarterly.sort(
        key=lambda item: ((item.get("year") or 0) * 10) + (item.get("quarter") or 0),
        reverse=True,
    )
    return {"annual": annual, "quarterly": quarterly}


def _trial_to_payload(trial: PharmaTrial) -> Dict[str, object]:
    raw_status = trial.status
    category = classify_status(raw_status)
    is_active = bool(trial.is_active)
    if is_active and category not in {"active", "commercial"}:
        category = "active"
    if not is_active and category == "active":
        category = "historical"

    payload: Dict[str, object] = {
        "id": trial.id,
        "nct_id": trial.nct_id,
        "title": trial.title,
        "phase": trial.phase,
        "phase_rank": _phase_rank(trial.phase),
        "status": _friendly_status(raw_status),
        "status_raw": raw_status,
        "category": category,
        "is_active": is_active,
        "condition": trial.condition,
        "estimated_completion": trial.estimated_completion,
        "start_date": trial.start_date,
        "enrollment": trial.enrollment,
        "success_probability": float(trial.success_probability) if trial.success_probability is not None else None,
        "sponsor": trial.sponsor,
        "location": trial.location,
        "source_url": trial.source_url,
        "last_refreshed": trial.last_refreshed,
        "has_results": trial.has_results,
        "why_stopped": trial.why_stopped,
        "outcome": _outcome_text(raw_status, trial.why_stopped, trial.has_results),
        "status_last_verified": trial.status_last_verified,
        "data_source": "stored",
    }
    return payload


def _record_to_payload(record: Dict[str, object]) -> Dict[str, object]:
    raw_status = record.get("status")
    category = record.get("status_category") or classify_status(raw_status)
    is_active = category == "active"
    payload: Dict[str, object] = {
        "id": None,
        "nct_id": record.get("nct_id"),
        "title": record.get("title"),
        "phase": record.get("phase"),
        "phase_rank": _phase_rank(record.get("phase")),
        "status": _friendly_status(raw_status),
        "status_raw": raw_status,
        "category": category,
        "is_active": is_active,
        "condition": ", ".join(record.get("conditions") or []),
        "estimated_completion": record.get("estimated_completion"),
        "start_date": record.get("start_date"),
        "enrollment": record.get("enrollment"),
        "success_probability": record.get("success_probability"),
        "sponsor": record.get("lead_sponsor"),
        "location": record.get("location"),
        "source_url": record.get("source_url"),
        "last_refreshed": None,
        "has_results": record.get("has_results"),
        "why_stopped": record.get("why_stopped"),
        "outcome": _outcome_text(raw_status, record.get("why_stopped"), record.get("has_results")),
        "status_last_verified": record.get("status_last_verified"),
        "data_source": "live",
    }
    return payload


def _summarize_payloads(
    *,
    payloads: List[Dict[str, object]],
    metadata: Optional[PharmaDrugMetadata],
    base_indication: Optional[str],
    base_label: Optional[str],
) -> Tuple[Dict[str, object], Optional[str], Optional[str]]:

    sorted_payloads = sorted(payloads, key=_payload_sort_tuple, reverse=True)
    active_payloads = [p for p in sorted_payloads if p.get("is_active")]
    best_payload = active_payloads[0] if active_payloads else (sorted_payloads[0] if sorted_payloads else None)

    label = metadata.label if metadata and metadata.label else base_label
    stage_override = metadata.phase_override if metadata else None
    probability_override = float(metadata.probability_override) if metadata and metadata.probability_override is not None else None
    peak_sales = float(metadata.peak_sales) if metadata and metadata.peak_sales is not None else None
    peak_sales_currency = metadata.peak_sales_currency if metadata else None
    peak_sales_year = metadata.peak_sales_year if metadata else None

    probability = probability_override
    probability_source: Optional[str] = "override" if probability_override is not None else None
    if probability is None:
        search_space = [best_payload] if best_payload else []
        search_space += sorted_payloads
        for payload in search_space:
            if not payload:
                continue
            value = payload.get("success_probability")
            if value is None:
                continue
            probability = float(value)
            probability_source = "trial"
            break

    expected_value: Optional[float] = None
    if probability is not None and peak_sales is not None:
        expected_value = round(peak_sales * (probability / 100.0), 2)

    is_commercial = bool(metadata.is_commercial) if metadata else False
    if not is_commercial:
        is_commercial = any(p.get("category") == "commercial" for p in sorted_payloads)
    if is_commercial and not label:
        label = "Commercial"

    stage = stage_override or (best_payload.get("phase") if best_payload else None)
    if is_commercial and not stage:
        stage = "Commercial"
    if not stage:
        for payload in sorted_payloads:
            phase = payload.get("phase")
            if phase:
                stage = phase
                break

    status = best_payload.get("status") if best_payload else None
    indication = base_indication or (best_payload.get("condition") if best_payload else None)

    sales_payload = _serialize_sales(metadata)

    summary = {
        "stage": stage,
        "status": status,
        "probability": probability,
        "probability_source": probability_source,
        "peak_sales": peak_sales,
        "peak_sales_currency": peak_sales_currency,
        "peak_sales_year": peak_sales_year,
        "expected_value": expected_value,
        "expected_value_currency": peak_sales_currency,
        "is_commercial": is_commercial,
        "label": label,
        "active_trial_count": sum(1 for p in sorted_payloads if p.get("is_active")),
        "total_trial_count": len(sorted_payloads),
        "primary_nct_id": best_payload.get("nct_id") if best_payload else None,
        "primary_estimated_completion": best_payload.get("estimated_completion") if best_payload else None,
        "primary_success_probability": best_payload.get("success_probability") if best_payload else None,
        "primary_start_date": best_payload.get("start_date") if best_payload else None,
        "notes": metadata.notes if metadata and metadata.notes else None,
        "metadata_source": "manual" if metadata else None,
        "segment": metadata.segment if metadata and metadata.segment else None,
        "sales": sales_payload,
    }

    return summary, label, indication


def _build_drug_response(
    *,
    drug_id: Optional[int],
    name: str,
    metadata: Optional[PharmaDrugMetadata],
    payloads: List[Dict[str, object]],
    base_indication: Optional[str],
    base_display_name: str,
    base_label: Optional[str],
) -> Dict[str, object]:
    summary, label, indication = _summarize_payloads(
        payloads=payloads,
        metadata=metadata,
        base_indication=base_indication,
        base_label=base_label,
    )

    display_name = metadata.display_name if metadata and metadata.display_name else base_display_name
    sales_payload = summary.get("sales") or {"annual": [], "quarterly": []}

    sorted_payloads = sorted(payloads, key=_payload_sort_tuple, reverse=True)
    active_payloads = [
        _clean_payload(p)
        for p in sorted_payloads
        if p.get("is_active")
    ]
    historical_payloads = [
        _clean_payload(p)
        for p in sorted_payloads
        if not p.get("is_active")
    ]

    return {
        "id": drug_id,
        "name": name,
        "display_name": display_name,
        "label": label,
        "indication": indication,
        "summary": summary,
        "sales": sales_payload,
        "active_trials": active_payloads,
        "historical_trials": historical_payloads,
    }


def _compute_company_summary(drugs: List[Dict[str, object]]) -> Dict[str, object]:
    expected_by_currency: Dict[str, float] = defaultdict(float)
    peak_by_currency: Dict[str, float] = defaultdict(float)
    active_trials = 0
    active_drugs = 0
    commercial_assets = 0
    total_trials = 0
    latest_sales_by_currency: Dict[str, float] = defaultdict(float)

    for drug in drugs:
        summary = drug.get("summary") or {}
        active_count = int(summary.get("active_trial_count") or 0)
        active_trials += active_count
        if active_count > 0:
            active_drugs += 1
        total_trials += int(summary.get("total_trial_count") or 0)
        if summary.get("is_commercial"):
            commercial_assets += 1

        ev_currency = summary.get("expected_value_currency")
        ev_value = summary.get("expected_value")
        if ev_currency and ev_value is not None:
            expected_by_currency[ev_currency] += float(ev_value)

        peak_currency = summary.get("peak_sales_currency")
        peak_value = summary.get("peak_sales")
        if peak_currency and peak_value is not None:
            peak_by_currency[peak_currency] += float(peak_value)

        sales = summary.get("sales") or {}
        annual_sales = sales.get("annual") or []
        if annual_sales:
            latest = annual_sales[0]
            currency = latest.get("currency")
            revenue = latest.get("revenue")
            if currency and revenue is not None:
                latest_sales_by_currency[currency] += float(revenue)

    return {
        "total_drugs": len(drugs),
        "total_trials": total_trials,
        "active_trials": active_trials,
        "active_drug_count": active_drugs,
        "commercial_assets": commercial_assets,
        "expected_value_by_currency": {k: round(v, 2) for k, v in expected_by_currency.items()},
        "peak_sales_by_currency": {k: round(v, 2) for k, v in peak_by_currency.items()},
        "latest_annual_sales_by_currency": {k: round(v, 2) for k, v in latest_sales_by_currency.items()},
    }


def _is_legacy_drug(drug: Dict[str, object]) -> bool:
    summary = drug.get("summary") or {}
    if summary.get("segment") == "legacy":
        return True
    if summary.get("is_commercial"):
        return False
    if summary.get("active_trial_count", 0) > 0:
        return False
    if summary.get("metadata_source") == "manual" and summary.get("probability") is not None:
        return False
    active_trials = drug.get("active_trials") or []
    if any(trial.get("is_active") for trial in active_trials):
        return False
    return True


def _openai_client() -> Optional[OpenAI]:
    if not settings.pharma_openai_api_key:
        return None
    return OpenAI(api_key=settings.pharma_openai_api_key)


def _serialize_drug(drug: PharmaDrug, metadata_map: Dict[str, PharmaDrugMetadata]) -> Dict[str, object]:
    meta = metadata_map.get(drug.name.lower())
    payloads = [_trial_to_payload(trial) for trial in drug.trials]
    return _build_drug_response(
        drug_id=drug.id,
        name=drug.name,
        metadata=meta,
        payloads=payloads,
        base_indication=drug.indication,
        base_display_name=drug.name,
        base_label=meta.label if meta else None,
    )


def _serialize_live_drug(
    drug_name: str,
    records: List[Dict[str, object]],
    metadata_map: Dict[str, PharmaDrugMetadata],
) -> Dict[str, object]:
    meta = metadata_map.get(drug_name.lower())
    payloads = [_record_to_payload(record) for record in records]
    indication = ", ".join(records[0].get("conditions") or []) if records else None
    return _build_drug_response(
        drug_id=None,
        name=drug_name,
        metadata=meta,
        payloads=payloads,
        base_indication=indication,
        base_display_name=drug_name,
        base_label=meta.label if meta else None,
    )


def _generate_analysis(company: Company, drugs: List[Dict[str, object]]) -> Optional[str]:
    client = _openai_client()
    if not client:
        return None

    drug_lines = []
    for drug in drugs:
        summary = drug.get("summary") or {}
        trials = drug.get("active_trials") or []
        if not trials:
            trials = drug.get("historical_trials") or []
        if not trials:
            continue
        primary = trials[0]
        stage = summary.get("stage") or primary.get("phase") or "Unknown Stage"
        status = primary.get("status") or "Status N/A"
        probability = summary.get("probability") or primary.get("success_probability")
        if isinstance(probability, (int, float)):
            prob_text = f"{float(probability):.1f}%"
        else:
            prob_text = "N/A"
        ev = summary.get("expected_value")
        currency = summary.get("expected_value_currency") or summary.get("peak_sales_currency")
        if ev is not None and currency:
            ev_text = f", EV {currency} {ev:,.0f}"
        elif ev is not None:
            ev_text = f", EV {ev:,.0f}"
        else:
            ev_text = ""
        name = drug.get("display_name") or drug.get("name") or "Unknown Drug"
        drug_lines.append(f"{name}: {stage} ({status}), success {prob_text}{ev_text}")

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
        record_openai_usage(
            endpoint=f"/pharma/{company.ticker}",
            api="responses",
            model="gpt-5",
            response=completion,
            success=True,
            metadata={"router": "pharma", "flow": "analysis"},
        )
        return completion.output_text
    except Exception as exc:
        record_openai_usage(
            endpoint=f"/pharma/{company.ticker}",
            api="responses",
            model="gpt-5",
            response=None,
            success=False,
            error=type(exc).__name__,
            metadata={"router": "pharma", "flow": "analysis"},
        )
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

    metadata_rows = (
        db.execute(
            select(PharmaDrugMetadata)
            .options(selectinload(PharmaDrugMetadata.sales))
            .where(PharmaDrugMetadata.ticker == pharma.ticker)
        )
        .scalars()
        .all()
    )
    metadata_map = {row.drug_name.lower(): row for row in metadata_rows}

    serialized_drugs = []
    existing_names: Dict[str, Dict[str, object]] = {}
    for drug in pharma.drugs:
        if drug.name and drug.name.lower() == "placebo":
            continue
        payload = _serialize_drug(drug, metadata_map)
        serialized_drugs.append(payload)
        existing_names[payload["name"].lower()] = payload
    # include metadata-defined assets even if no trials stored yet
    for key, meta in metadata_map.items():
        if key in existing_names:
            continue
        placeholder = _build_drug_response(
            drug_id=None,
            name=meta.drug_name,
            metadata=meta,
            payloads=[],
            base_indication=None,
            base_display_name=meta.display_name or meta.drug_name,
            base_label=meta.label,
        )
        serialized_drugs.append(placeholder)
        existing_names[key] = placeholder
    active_drugs: List[Dict[str, object]] = []
    legacy_drugs: List[Dict[str, object]] = []
    for payload in serialized_drugs:
        if _is_legacy_drug(payload):
            legacy_drugs.append(payload)
        else:
            active_drugs.append(payload)

    company_summary = _compute_company_summary(active_drugs)
    company_summary["legacy_drug_count"] = len(legacy_drugs)
    company_summary["legacy_trial_count"] = sum(
        len(drug.get("active_trials") or []) + len(drug.get("historical_trials") or [])
        for drug in legacy_drugs
    )
    live_trials = None
    if force_live or not active_drugs:
        try:
            studies, _ = fetch_studies(lead=pharma.lead_sponsor or company.name, page_size=100, max_pages=2)
            grouped = group_by_intervention(studies)
            live_drugs = []
            for drug_name, records in grouped.items():
                live_drugs.append(_serialize_live_drug(drug_name, records, metadata_map))
            live_trials = live_drugs
        except Exception:
            live_trials = None

    analysis = _generate_analysis(company, live_trials or active_drugs) if (live_trials or active_drugs) else None

    return {
        "company": {
            "id": company.id,
            "ticker": company.ticker,
            "name": company.name,
            "industry": company.industry_name,
            "lead_sponsor": pharma.lead_sponsor,
            "last_refreshed": pharma.last_refreshed.isoformat() if pharma.last_refreshed else None,
        },
        "drugs": active_drugs,
        "legacy_drugs": legacy_drugs,
        "live_drugs": live_trials,
        "summary": company_summary,
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
        record_openai_usage(
            endpoint="/pharma/chat",
            api="responses",
            model="gpt-5",
            response=completion,
            success=True,
            metadata={"router": "pharma", "flow": "chat"},
        )
        return {"response": completion.output_text}
    except Exception as exc:
        record_openai_usage(
            endpoint="/pharma/chat",
            api="responses",
            model="gpt-5",
            response=None,
            success=False,
            error=type(exc).__name__,
            metadata={"router": "pharma", "flow": "chat"},
        )
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {exc}") from exc
