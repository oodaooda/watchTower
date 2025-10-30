"""Parse ClinicalTrials.gov bulk XML dump and map to pharma companies."""
from __future__ import annotations

import json
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from dateutil import parser as date_parser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Company
from app.services.clinical_trials import (
    estimate_probability,
    format_phase,
    normalize_intervention_name,
    infer_phase_from_text,
)
from app.services.pharma_refresh import ensure_pharma_company, ingest_records


def load_sponsor_map(path: Path) -> Dict[str, Dict[str, List[str]]]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    normalized: Dict[str, Dict[str, List[str]]] = {}
    for ticker, payload in data.items():
        sponsors = [s.upper().strip() for s in payload.get("sponsors", [])]
        interventions = payload.get("interventions", [])
        normalized[ticker.upper()] = {
            "sponsors": [s for s in sponsors if s],
            "interventions": interventions,
        }
    return normalized


def parse_completion_date(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return date_parser.parse(text, fuzzy=True)
    except (TypeError, ValueError, OverflowError):
        return None


def parse_study_xml(xml_bytes: bytes) -> Optional[Dict[str, object]]:
    from xml.etree import ElementTree as ET

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    def text(path: str) -> Optional[str]:
        node = root.find(path)
        if node is not None and node.text:
            return node.text.strip()
        return None

    nct_id = text("id_info/nct_id")
    if not nct_id:
        return None

    lead_sponsor = text("sponsors/lead_sponsor/agency")
    status = text("overall_status")
    phase = format_phase(text("phase"))
    if not phase:
        inferred = infer_phase_from_text(text("brief_title") or "") or infer_phase_from_text(text("official_title") or "")
        if inferred:
            phase = inferred

    interventions = []
    for node in root.findall("intervention"):
        name = node.findtext("intervention_name") or node.findtext("description")
        cleaned = normalize_intervention_name(name)
        if cleaned:
            interventions.append(cleaned)

    conditions = [elem.text.strip() for elem in root.findall("condition") if elem.text]

    completion = parse_completion_date(text("primary_completion_date")) or parse_completion_date(
        text("completion_date")
    )

    enrollment = root.findtext("enrollment")
    try:
        enrollment_count = int(enrollment) if enrollment else None
    except ValueError:
        enrollment_count = None

    success_prob = estimate_probability(phase, status)

    return {
        "nct_id": nct_id,
        "brief_title": text("brief_title"),
        "official_title": text("official_title"),
        "phase": phase,
        "status": status,
        "conditions": conditions,
        "interventions": interventions,
        "estimated_completion": completion,
        "enrollment": enrollment_count,
        "success_probability": success_prob,
        "lead_sponsor": lead_sponsor,
        "location": text("location/facility/name"),
        "source_url": f"https://clinicaltrials.gov/study/{nct_id}",
    }


def index_sponsors(mapping: Dict[str, Dict[str, List[str]]]) -> Dict[str, str]:
    sponsor_to_ticker: Dict[str, str] = {}
    for ticker, payload in mapping.items():
        for sponsor in payload.get("sponsors", []):
            sponsor_to_ticker[sponsor.upper()] = ticker
    return sponsor_to_ticker


def match_ticker(record: Dict[str, object], sponsor_index: Dict[str, str], mapping: Dict[str, Dict[str, List[str]]]) -> Optional[str]:
    sponsor = (record.get("lead_sponsor") or "").upper().strip()
    if sponsor in sponsor_index:
        return sponsor_index[sponsor]

    # Try intervention aliases
    interventions = record.get("interventions") or []
    for ticker, payload in mapping.items():
        aliases = payload.get("interventions", [])
        for intervention in interventions:
            if any(alias.lower() in intervention.lower() for alias in aliases):
                return ticker
    return None


def parse_dump(zip_path: Path, mapping: Dict[str, Dict[str, List[str]]]) -> Dict[str, List[Dict[str, object]]]:
    sponsor_index = index_sponsors(mapping)
    per_ticker: Dict[str, List[Dict[str, object]]] = defaultdict(list)

    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".xml"):
                continue
            with archive.open(name) as handle:
                record = parse_study_xml(handle.read())
            if not record:
                continue
            ticker = match_ticker(record, sponsor_index, mapping)
            if not ticker:
                continue
            per_ticker[ticker].append(record)

    return per_ticker


def ingest_dump(session: Session, records: Dict[str, List[Dict[str, object]]]) -> None:
    for ticker, trials in records.items():
        company = session.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
        if not company:
            continue
        ensure_pharma_company(session, company, None)
        ingest_records(session, company, trials)
