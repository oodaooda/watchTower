"""Seed pharma tables using sponsor/intervention aliases from mapping file."""
from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import Company
from app.services.clinical_trials import fetch_studies
from app.services.pharma_refresh import ensure_pharma_company, ingest_records


def load_mapping(path: Path) -> Dict[str, Dict[str, List[str]]]:
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    mapping: Dict[str, Dict[str, List[str]]] = {}
    for ticker, payload in raw.items():
        sponsors = [s.strip() for s in payload.get("sponsors", []) if s and s.strip()]
        interventions = [s.strip() for s in payload.get("interventions", []) if s and s.strip()]
        conditions = [s.strip() for s in payload.get("conditions", []) if s and s.strip()]
        mapping[ticker.upper()] = {
            "sponsors": sponsors,
            "interventions": interventions,
            "conditions": conditions,
        }
    return mapping


def _normalize(text: str) -> str:
    return re.sub(r"\W+", "", text).upper()


def _build_expected_sponsors(company: Company, aliases: Dict[str, List[str]]) -> List[str]:
    expected: List[str] = []
    if company.name:
        expected.append(company.name)
    for item in aliases.get("sponsors", []):
        if item:
            expected.append(item)
    return expected


def _matches_expected_sponsor(record: dict, expected: List[str]) -> bool:
    if not expected:
        return True
    sponsor = record.get("lead_sponsor") or ""
    if not sponsor:
        return True
    normalized = _normalize(sponsor)
    for candidate in expected:
        cand_norm = _normalize(candidate)
        if not cand_norm:
            continue
        if normalized == cand_norm:
            return True
        if cand_norm in normalized or normalized in cand_norm:
            return True
    return False


def collect_records(company: Company, aliases: Dict[str, List[str]]) -> List[dict]:
    seen: OrderedDict[str, dict] = OrderedDict()
    expected_sponsors = _build_expected_sponsors(company, aliases)

    def add_records(studies: List[dict]):
        for record in studies:
            if record.get("is_interventional") is False:
                continue
            if not _matches_expected_sponsor(record, expected_sponsors):
                continue
            nct_id = record.get("nct_id")
            if not nct_id:
                continue
            if nct_id not in seen:
                seen[nct_id] = record

    for sponsor in aliases.get("sponsors", []):
        studies, _ = fetch_studies(lead=sponsor, page_size=200, max_pages=3)
        add_records(studies)

    for intervention in aliases.get("interventions", []):
        studies, _ = fetch_studies(intervention=intervention, page_size=200, max_pages=2)
        add_records(studies)

    for condition in aliases.get("conditions", []):
        studies, _ = fetch_studies(condition=condition, page_size=200, max_pages=1)
        add_records(studies)

    return list(seen.values())


def seed_company(session: Session, company: Company, aliases: Dict[str, List[str]]) -> int:
    ensure_pharma_company(session, company, None)
    records = collect_records(company, aliases)
    if not records:
        return 0
    return ingest_records(session, company, records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed pharma tables from mapping file via ClinicalTrials.gov API")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("ops/data/pharma_sponsor_map.json"),
        help="Path to sponsor/intervention mapping JSON",
    )
    parser.add_argument("--tickers", nargs="*", help="Optional subset of tickers to seed")
    args = parser.parse_args()

    mapping = load_mapping(args.mapping)
    if not mapping:
        print("Mapping file empty; nothing to do.")
        return

    scope = {t.upper() for t in args.tickers} if args.tickers else None

    session: Session = SessionLocal()
    try:
        for ticker, aliases in mapping.items():
            if scope and ticker not in scope:
                continue
            company = session.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
            if not company:
                print(f"[skip] {ticker}: company not found")
                continue
            try:
                count = seed_company(session, company, aliases)
                print(f"[ok] {ticker}: ingested {count} trials")
            except Exception as exc:
                session.rollback()
                print(f"[error] {ticker}: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
