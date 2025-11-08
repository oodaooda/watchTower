"""Utilities for fetching and normalising clinical trial data."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Dict, Iterable, List, Optional, Tuple

import httpx

CLINICAL_TRIALS_API = "https://clinicaltrials.gov/api/v2/studies"

# Rough success probability heuristics per phase
PHASE_SUCCESS_PROBABILITIES: Dict[str, float] = {
    "Phase 1": 0.60,
    "Phase 1/Phase 2": 0.55,
    "Phase 2": 0.35,
    "Phase 2/Phase 3": 0.45,
    "Phase 3": 0.65,
    "Phase 4": 0.85,
    "Early Phase 1": 0.25,
    "N/A": 0.30,
}


class ClinicalTrialRecord(Dict[str, object]):
    """Typed dict wrapper for clarity."""


ACTIVE_STATUSES = {
    "RECRUITING",
    "ACTIVE, NOT RECRUITING",
    "ENROLLING BY INVITATION",
    "NOT YET RECRUITING",
    "AVAILABLE",
}

COMMERCIAL_STATUSES = {
    "APPROVED FOR MARKETING",
}

NEGATIVE_STATUSES = {
    "TERMINATED",
    "WITHDRAWN",
    "SUSPENDED",
}

HISTORICAL_STATUSES = {
    "COMPLETED",
    "UNKNOWN STATUS",
    "NO LONGER AVAILABLE",
}


def is_active_status(status: Optional[str]) -> bool:
    if not status:
        return False
    value = status.strip().upper()
    if value in COMMERCIAL_STATUSES:
        return False
    if value in NEGATIVE_STATUSES:
        return False
    return value in ACTIVE_STATUSES


def is_commercial_status(status: Optional[str]) -> bool:
    if not status:
        return False
    return status.strip().upper() in COMMERCIAL_STATUSES


def status_category(status: Optional[str]) -> str:
    if is_commercial_status(status):
        return "commercial"
    if is_active_status(status):
        return "active"
    if not status:
        return "unknown"
    value = status.strip().upper()
    if value in NEGATIVE_STATUSES:
        return "terminated"
    if value in HISTORICAL_STATUSES:
        return "historical"
    if "COMPLETED" in value:
        return "historical"
    return "other"


def _parse_date(date_struct: Optional[Dict[str, str]]) -> Optional[datetime]:
    if not date_struct:
        return None
    value = date_struct.get("date")
    if not value:
        return None
    for fmt in ("%Y-%m", "%Y-%m-%d", "%B %Y", "%b %Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _extract_interventions(
    protocol_section: Dict[str, object],
) -> List[str]:
    module = protocol_section.get("armsInterventionsModule") or {}
    interventions = module.get("interventions") or []
    names: List[str] = []
    for item in interventions:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or ""
        description = item.get("description") or ""
        cleaned = _normalize_intervention_name((name or "").strip()) or _normalize_intervention_name(description.strip())
        if cleaned:
            names.append(cleaned)
    return names


def _extract_conditions(protocol_section: Dict[str, object]) -> List[str]:
    cond_module = protocol_section.get("conditionsModule") or {}
    conditions = cond_module.get("conditions") or []
    return [c.strip() for c in conditions if isinstance(c, str)]


def _extract_lead_sponsor(protocol_section: Dict[str, object]) -> Optional[str]:
    sponsor_module = protocol_section.get("sponsorCollaboratorsModule") or {}
    lead = sponsor_module.get("leadSponsor") or {}
    name = lead.get("name")
    return name.strip() if isinstance(name, str) else None


def estimate_probability(phase: Optional[str], status: Optional[str]) -> Optional[float]:
    category = status_category(status)
    if category == "commercial":
        return 95.0

    probability: Optional[float] = None
    if phase:
        probability = PHASE_SUCCESS_PROBABILITIES.get(phase)
        if probability is None:
            # Attempt to match partial phase names
            for key, value in PHASE_SUCCESS_PROBABILITIES.items():
                if key.lower() in phase.lower():
                    probability = value
                    break

    if probability is None:
        # If we have a meaningful status but no phase, fall back to conservative defaults
        if category == "active":
            probability = 0.3
        elif category == "historical":
            probability = 0.2
        elif category == "terminated":
            probability = 0.05
        else:
            return None

    status_lower = status.lower() if status else ""
    if category == "active":
        if "not yet recruiting" in status_lower:
            probability *= 0.85
        elif "recruiting" in status_lower or "enrolling" in status_lower:
            probability *= 1.05
        elif "active, not recruiting" in status_lower:
            probability *= 1.02
    elif category == "historical":
        probability = min(probability, 0.35)
    elif category == "terminated":
        probability = min(probability, 0.1)
    elif category in {"other", "unknown"}:
        probability = min(probability, 0.25)

    probability = max(0.01, min(probability, 0.99))
    return round(probability * 100, 2)


def _estimate_probability(phase: Optional[str], status: Optional[str]) -> Optional[float]:
    return estimate_probability(phase, status)


def normalise_study(study: Dict[str, object]) -> ClinicalTrialRecord:
    protocol = study.get("protocolSection") or {}
    identification = protocol.get("identificationModule") or {}
    status_module = protocol.get("statusModule") or {}
    design_module = protocol.get("designModule") or {}
    nct_id = identification.get("nctId")
    title = identification.get("briefTitle")

    phase_info = design_module.get("phaseInfo", {}) or {}
    phase = _format_phase(phase_info.get("phase") or phase_info.get("phaseDescription"))
    status = status_module.get("overallStatus")

    primary_completion = _parse_date(status_module.get("primaryCompletionDateStruct"))
    completion_date = _parse_date(status_module.get("completionDateStruct"))
    estimated_completion = primary_completion or completion_date
    status_verified = _parse_date(status_module.get("statusVerifiedDateStruct"))
    last_update_posted = _parse_date(status_module.get("lastUpdatePostDateStruct"))
    start_date = _parse_date(status_module.get("startDateStruct"))

    enrollment_info = design_module.get("enrollmentInfo") or {}
    enrollment = enrollment_info.get("count")
    if isinstance(enrollment, str) and enrollment.isdigit():
        enrollment = int(enrollment)

    conditions = _extract_conditions(protocol)
    interventions = _extract_interventions(protocol)
    lead_sponsor = _extract_lead_sponsor(protocol)

    success_probability = _estimate_probability(phase, status)

    location_module = protocol.get("contactsLocationsModule") or {}
    locations = location_module.get("locations") or []
    first_location = locations[0]["facility"]["name"] if locations else None
    why_stopped = status_module.get("whyStopped")
    has_results = bool(study.get("resultsSection"))
    study_type = (design_module.get("studyType") or "").strip()
    is_interventional = (study_type or "").lower() != "observational"

    record: ClinicalTrialRecord = {
        "nct_id": nct_id,
        "brief_title": title,
        "title": title,
        "official_title": identification.get("officialTitle"),
        "phase": phase,
        "status": status,
        "conditions": conditions,
        "interventions": interventions,
        "estimated_completion": estimated_completion,
        "enrollment": enrollment if isinstance(enrollment, int) else None,
        "success_probability": success_probability,
        "lead_sponsor": lead_sponsor,
        "location": first_location,
        "source_url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None,
        "has_results": has_results,
        "why_stopped": why_stopped,
        "status_last_verified": status_verified or last_update_posted,
        "status_last_updated": last_update_posted,
        "study_type": study_type,
        "is_interventional": is_interventional,
        "status_category": status_category(status),
        "start_date": start_date,
    }
    record["is_active"] = record["status_category"] == "active"

    if not record["phase"]:
        inferred_phase = _infer_phase_from_text(record.get("brief_title") or "") or _infer_phase_from_text(
            record.get("official_title") or ""
        )
        if inferred_phase:
            record["phase"] = inferred_phase

    return record


def fetch_studies(
    *,
    lead: Optional[str] = None,
    condition: Optional[str] = None,
    intervention: Optional[str] = None,
    status: Optional[str] = None,
    page_size: int = 100,
    max_pages: Optional[int] = None,
) -> Tuple[List[ClinicalTrialRecord], Dict[str, object]]:
    """Fetch studies from ClinicalTrials.gov using the v2 API."""
    params: Dict[str, str] = {"pageSize": str(page_size), "countTotal": "true"}
    if lead:
        params["query.lead"] = lead
    if condition:
        params["query.cond"] = condition
    if intervention:
        params["query.intr"] = intervention
    if status:
        params["filter.overallStatus"] = status

    client = httpx.Client(timeout=30.0)
    studies: List[ClinicalTrialRecord] = []
    meta: Dict[str, object] = {}
    page_count = 0
    try:
        while True:
            response = client.get(CLINICAL_TRIALS_API, params=params)
            response.raise_for_status()
            payload = response.json()
            raw_studies = payload.get("studies") or []
            meta = payload.get("meta") or {}

            for item in raw_studies:
                try:
                    studies.append(normalise_study(item))
                except Exception:
                    # Skip malformed entries but continue
                    continue

            page_count += 1
            next_token = payload.get("nextPageToken")
            if not next_token:
                break
            if max_pages and page_count >= max_pages:
                break
            params["pageToken"] = next_token
    finally:
        client.close()

    return studies, meta


def group_by_intervention(
    records: Iterable[ClinicalTrialRecord],
) -> Dict[str, List[ClinicalTrialRecord]]:
    grouped: Dict[str, List[ClinicalTrialRecord]] = {}
    for record in records:
        interventions = record.get("interventions") or []
        if not interventions:
            interventions = ["Unknown Intervention"]
        for intervention in interventions:
            grouped.setdefault(intervention, []).append(record)
    for key, items in grouped.items():
        items.sort(key=_record_sort_key)
    return grouped


def normalize_intervention_name(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    name = raw.strip()
    if not name:
        return None
    # Remove generic prefixes like "active drug"
    name = re.sub(r"(?i)^(active|study) drug\s*", "", name)
    # Prefer content in parentheses if present
    match = re.search(r"\(([^)]+)\)", name)
    if match and len(match.group(1)) > 3:
        name = match.group(1).strip()
    # Collapse extra spaces
    name = re.sub(r"\s+", " ", name)
    return name or None


def _normalize_intervention_name(raw: Optional[str]) -> Optional[str]:
    return normalize_intervention_name(raw)


def _format_phase(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    s = str(value).replace("_", " ").replace("-", " ").strip().upper()
    mappings = {
        "PHASE1": "Phase 1",
        "PHASE 1": "Phase 1",
        "PHASE2": "Phase 2",
        "PHASE 2": "Phase 2",
        "PHASE3": "Phase 3",
        "PHASE 3": "Phase 3",
        "PHASE4": "Phase 4",
        "PHASE 4": "Phase 4",
        "EARLY PHASE 1": "Early Phase 1",
        "PHASE 1/PHASE 2": "Phase 1/Phase 2",
        "PHASE 2/PHASE 3": "Phase 2/Phase 3",
        "PHASE 3/PHASE 4": "Phase 3/Phase 4",
        "NA": "N/A",
        "N/A": "N/A",
        "FDA REVIEW": "FDA Review",
        "APPROVED": "Approved",
    }
    if s in mappings:
        return mappings[s]
    if s.startswith("PHASE "):
        rest = s.split(" ", 1)[1]
        return f"Phase {rest.title()}"
    if "/" in s:
        parts = [p.strip().title() for p in s.split("/") if p.strip()]
        if parts:
            return "/".join(parts)
    return s.title()


def format_phase(value: Optional[str]) -> Optional[str]:
    return _format_phase(value)


PHASE_REGEX = re.compile(r"phase\s*(I{1,4}|V|1/2|2/3|3/4|1|2|3|4)", re.IGNORECASE)

STATUS_CATEGORY_ORDER = {
    "active": 0,
    "commercial": 1,
    "historical": 2,
    "terminated": 3,
    "other": 4,
    "unknown": 5,
}


def infer_phase_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    match = PHASE_REGEX.search(text)
    if not match:
        return None
    token = match.group(1).upper()
    mapping = {
        "I": "Phase 1",
        "II": "Phase 2",
        "III": "Phase 3",
        "IV": "Phase 4",
        "V": "Phase 5",
        "1": "Phase 1",
        "2": "Phase 2",
        "3": "Phase 3",
        "4": "Phase 4",
        "1/2": "Phase 1/Phase 2",
        "2/3": "Phase 2/Phase 3",
        "3/4": "Phase 3/Phase 4",
    }
    if token in mapping:
        return mapping[token]
    if token.startswith("I"):
        return f"Phase {len(token)}"
    return f"Phase {token}"


def _infer_phase_from_text(text: str) -> Optional[str]:
    return infer_phase_from_text(text)


def _record_sort_key(record: ClinicalTrialRecord) -> Tuple[int, float, float]:
    category = str(record.get("status_category") or "unknown").lower()
    rank = STATUS_CATEGORY_ORDER.get(category, 99)
    verified = record.get("status_last_verified")
    if isinstance(verified, datetime):
        verified_value = -verified.timestamp()
    else:
        verified_value = float("inf")
    probability = record.get("success_probability")
    probability_value = -(float(probability) if isinstance(probability, (int, float)) else 0.0)
    return (rank, verified_value, probability_value)
