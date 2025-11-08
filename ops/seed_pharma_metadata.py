"""Seed pharma_drug_metadata entries from structured JSON."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import Company, PharmaDrugMetadata, PharmaDrugSales


METADATA_FIELDS = (
    "display_name",
    "label",
    "notes",
    "phase_override",
    "is_commercial",
    "peak_sales",
    "peak_sales_currency",
    "peak_sales_year",
    "probability_override",
    "segment",
)

NUMERIC_FIELDS = {"peak_sales", "probability_override"}
BOOL_FIELDS = {"is_commercial"}


@dataclass
class MetadataRecord:
    ticker: str
    drug_name: str
    payload: Dict[str, object]

    @property
    def key(self) -> str:
        return f"{self.ticker}:{self.drug_name}"


def load_metadata(path: Path) -> Iterable[MetadataRecord]:
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    for ticker, entries in raw.items():
        ticker_upper = ticker.upper().strip()
        if not ticker_upper:
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            drug_name = (entry.get("drug_name") or "").strip()
            if not drug_name:
                continue
            payload = {k: v for k, v in entry.items() if k != "drug_name"}
            yield MetadataRecord(ticker=ticker_upper, drug_name=drug_name, payload=payload)


def ensure_company(session: Session, ticker: str) -> Optional[Company]:
    stmt = select(Company).where(Company.ticker == ticker)
    return session.execute(stmt).scalar_one_or_none()


def upsert_metadata(session: Session, record: MetadataRecord, *, dry_run: bool = False) -> bool:
    stmt = select(PharmaDrugMetadata).where(
        PharmaDrugMetadata.ticker == record.ticker,
        PharmaDrugMetadata.drug_name == record.drug_name,
    )
    metadata = session.execute(stmt).scalar_one_or_none()
    created = False
    if not metadata:
        metadata = PharmaDrugMetadata(ticker=record.ticker, drug_name=record.drug_name)
        session.add(metadata)
        created = True

    payload = dict(record.payload)
    sales_payload = payload.pop("sales", None)

    for field in METADATA_FIELDS:
        if field in payload:
            value = payload[field]
            if field in NUMERIC_FIELDS and value is not None:
                value = Decimal(str(value))
            if field in BOOL_FIELDS and value is not None:
                value = bool(value)
            setattr(metadata, field, value)

    session.flush()

    if sales_payload is not None:
        session.query(PharmaDrugSales).filter(PharmaDrugSales.metadata_id == metadata.id).delete()

        for item in sales_payload.get("annual", []):
            year = item.get("year")
            revenue = item.get("revenue")
            if year is None or revenue is None:
                continue
            sale = PharmaDrugSales(
                metadata_id=metadata.id,
                period_type="annual",
                period_year=int(year),
                period_quarter=None,
                revenue=Decimal(str(revenue)),
                currency=(item.get("currency") or metadata.peak_sales_currency or "USD")[:3].upper(),
                source=item.get("source"),
            )
            session.add(sale)

        for item in sales_payload.get("quarterly", []):
            year = item.get("year")
            quarter = item.get("quarter")
            revenue = item.get("revenue")
            if year is None or quarter is None or revenue is None:
                continue
            sale = PharmaDrugSales(
                metadata_id=metadata.id,
                period_type="quarterly",
                period_year=int(year),
                period_quarter=int(quarter),
                revenue=Decimal(str(revenue)),
                currency=(item.get("currency") or metadata.peak_sales_currency or "USD")[:3].upper(),
                source=item.get("source"),
            )
            session.add(sale)

    if dry_run:
        session.rollback()
    else:
        session.flush()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed pharma drug metadata overrides.")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("ops/data/pharma_drug_metadata.json"),
        help="Path to metadata JSON file.",
    )
    parser.add_argument("--tickers", nargs="*", help="Optional subset of tickers to seed.")
    parser.add_argument("--dry-run", action="store_true", help="Load file and report actions without committing.")
    args = parser.parse_args()

    if not args.mapping.exists():
        raise SystemExit(f"Metadata file not found: {args.mapping}")

    scope = {t.upper() for t in args.tickers} if args.tickers else None
    records = list(load_metadata(args.mapping))
    if scope:
        records = [record for record in records if record.ticker in scope]
    if not records:
        print("No metadata records to process.")
        return

    session: Session = SessionLocal()
    try:
        processed = 0
        created = 0
        skipped = 0
        for record in records:
            company = ensure_company(session, record.ticker)
            if not company:
                print(f"[skip] {record.ticker}: company not found in database")
                skipped += 1
                continue
            was_created = upsert_metadata(session, record, dry_run=args.dry_run)
            processed += 1
            created += 1 if was_created else 0
            action = "created" if was_created else "updated"
            suffix = " (dry-run)" if args.dry_run else ""
            print(f"[{action}] {record.key}{suffix}")

        if args.dry_run:
            session.rollback()
        else:
            session.commit()
        print(
            f"Done. processed={processed} created={created} skipped={skipped}{' (dry-run, no changes committed)' if args.dry_run else ''}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
