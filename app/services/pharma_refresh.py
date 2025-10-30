"""Shared helpers for refreshing pharma data."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import (
    Company,
    PharmaCompany,
    PharmaDrug,
    PharmaTrial,
)
from app.services.clinical_trials import fetch_studies, group_by_intervention

PHARMA_KEYWORDS = ("pharma", "pharmaceutical", "biotech", "drug")
ORG_SUFFIXES = (
    " INC",
    " INC.",
    ", INC",
    ", INC.",
    " CORPORATION",
    " CORP",
    " CORP.",
    ", CORP",
    ", CORP.",
    " COMPANY",
    " CO",
    " CO.",
    ", CO",
    ", CO.",
    " LTD",
    " LTD.",
    ", LTD",
    ", LTD.",
    " PLC",
    ", PLC",
    " AG",
    ", AG",
)


def is_pharma_company(company: Company) -> bool:
    haystack = " ".join(
        filter(
            None,
            [
                company.industry_name.lower() if company.industry_name else "",
                str(company.sic or ""),
            ],
        )
    )
    return any(keyword in haystack for keyword in PHARMA_KEYWORDS)


def get_target_companies(session: Session, ticker: Optional[str], include_all: bool) -> List[Company]:
    if ticker:
        stmt = select(Company).where(Company.ticker == ticker.upper())
        company = session.execute(stmt).scalar_one_or_none()
        if not company:
            raise ValueError(f"Ticker {ticker} not found.")
        return [company]

    stmt = select(Company).where(Company.is_tracked.is_(True))
    companies = session.execute(stmt).scalars().all()
    if include_all:
        return companies
    return [c for c in companies if is_pharma_company(c)]


def _normalize_lead(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    upper = cleaned.upper()
    for suffix in ORG_SUFFIXES:
        if upper.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip(" ,")
            upper = cleaned.upper()
    return cleaned or None


def _lead_candidates(company: Company, override: Optional[str]) -> List[str]:
    candidates: List[str] = []
    seen = set()

    def add(val: Optional[str]):
        if not val:
            return
        key = val.lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(val)

    add(override)
    add(_normalize_lead(override))
    add(company.name.strip() if company.name else None)
    add(_normalize_lead(company.name) if company.name else None)
    add(company.ticker.strip() if company.ticker else None)
    if company.name and "," in company.name:
        add(company.name.replace(",", ""))
        add(_normalize_lead(company.name.replace(",", "")))
    return [c for c in candidates if c]


def ensure_pharma_company(session: Session, company: Company, lead_sponsor: Optional[str]) -> PharmaCompany:
    stmt = select(PharmaCompany).where(PharmaCompany.company_id == company.id)
    pharma = session.execute(stmt).scalar_one_or_none()
    if pharma:
        if lead_sponsor:
            pharma.lead_sponsor = lead_sponsor
        return pharma

    pharma = PharmaCompany(
        company_id=company.id,
        ticker=company.ticker,
        lead_sponsor=lead_sponsor or company.name,
        last_refreshed=None,
    )
    session.add(pharma)
    session.flush()
    return pharma


def _ensure_pharma_company(session: Session, company: Company, lead_sponsor: Optional[str]) -> PharmaCompany:
    return ensure_pharma_company(session, company, lead_sponsor)


def ensure_drug(
    session: Session,
    pharma_company: PharmaCompany,
    drug_name: str,
    indication: Optional[str],
    cache: Optional[Dict[str, PharmaDrug]] = None,
) -> PharmaDrug:
    key = drug_name.lower()
    if cache is not None and key in cache:
        drug = cache[key]
        if indication:
            drug.indication = indication
        return drug

    stmt = (
        select(PharmaDrug)
        .where(
            PharmaDrug.pharma_company_id == pharma_company.id,
            PharmaDrug.name == drug_name,
        )
    )
    drug = session.execute(stmt).scalar_one_or_none()
    if drug:
        if indication:
            drug.indication = indication
        if cache is not None:
            cache[key] = drug
        return drug

    drug = PharmaDrug(pharma_company_id=pharma_company.id, name=drug_name, indication=indication)
    session.add(drug)
    session.flush()
    if cache is not None:
        cache[key] = drug
    return drug


def _ensure_drug(
    session: Session,
    pharma_company: PharmaCompany,
    drug_name: str,
    indication: Optional[str],
    cache: Optional[Dict[str, PharmaDrug]] = None,
) -> PharmaDrug:
    return ensure_drug(session, pharma_company, drug_name, indication, cache)


def upsert_trial(session: Session, drug: PharmaDrug, record: dict) -> PharmaTrial:
    nct_id = record.get("nct_id")
    if not nct_id:
        raise ValueError("Missing nct_id in trial record.")

    stmt = select(PharmaTrial).where(PharmaTrial.nct_id == nct_id)
    trial = session.execute(stmt).scalar_one_or_none()
    if not trial:
        trial = PharmaTrial(pharma_drug_id=drug.id, nct_id=nct_id)
        session.add(trial)
        session.flush()

    trial.pharma_drug_id = drug.id
    trial.title = record.get("title")
    trial.phase = record.get("phase")
    trial.status = record.get("status")
    trial.condition = ", ".join(record.get("conditions") or [])
    completion = record.get("estimated_completion")
    trial.estimated_completion = completion.date() if hasattr(completion, "date") else completion
    trial.enrollment = record.get("enrollment")
    trial.success_probability = record.get("success_probability")
    trial.sponsor = record.get("lead_sponsor")
    trial.location = record.get("location")
    trial.source_url = record.get("source_url")
    trial.last_refreshed = datetime.utcnow()

    return trial


def _upsert_trial(session: Session, drug: PharmaDrug, record: dict) -> PharmaTrial:
    return upsert_trial(session, drug, record)


def refresh_company(
    session: Session,
    company: Company,
    *,
    lead: Optional[str] = None,
    condition: Optional[str] = None,
    intervention: Optional[str] = None,
    status: Optional[str] = None,
    page_size: int = 100,
    max_pages: Optional[int] = None,
) -> int:
    studies = []
    meta = {}
    for lead_query in _lead_candidates(company, lead):
        try:
            studies, meta = fetch_studies(
                lead=lead_query,
                condition=condition,
                intervention=intervention,
                status=status,
                page_size=page_size,
                max_pages=max_pages,
            )
        except Exception:
            studies = []
        if studies:
            break

    if not studies:
        return 0

    first_lead = next((record.get("lead_sponsor") for record in studies if record.get("lead_sponsor")), None)
    ensure_pharma_company(session, company, first_lead)
    return ingest_records(session, company, studies, lead_sponsor_override=first_lead)


def ingest_records(
    session: Session,
    company: Company,
    records: List[dict],
    *,
    lead_sponsor_override: Optional[str] = None,
) -> int:
    if not records:
        return 0

    grouped = group_by_intervention(records)
    first_lead = lead_sponsor_override or next((record.get("lead_sponsor") for record in records if record.get("lead_sponsor")), None)
    pharma_company = ensure_pharma_company(session, company, first_lead)

    drug_cache: Dict[str, PharmaDrug] = {d.name.lower(): d for d in pharma_company.drugs}
    processed_ids: set[str] = {trial.nct_id for d in pharma_company.drugs for trial in d.trials if trial.nct_id}

    total_trials = 0
    for drug_name, recs in grouped.items():
        drug = ensure_drug(
            session,
            pharma_company,
            drug_name,
            indication=", ".join(recs[0].get("conditions") or []),
            cache=drug_cache,
        )
        for record in recs:
            nct_id = record.get("nct_id")
            if not nct_id or nct_id in processed_ids:
                continue
            try:
                upsert_trial(session, drug, record)
                total_trials += 1
                processed_ids.add(nct_id)
            except ValueError:
                continue

    pharma_company.last_refreshed = datetime.utcnow()
    session.commit()
    return total_trials
