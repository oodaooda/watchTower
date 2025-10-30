"""Import ClinicalTrials.gov bulk dump into pharma tables."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import requests
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.ctgov_bulk import ingest_dump, load_sponsor_map, parse_dump

DEFAULT_DUMP_URL = "https://clinicaltrials.gov/AllPublicXML.zip"
DEFAULT_DATA_DIR = Path("ops/data/ctgov")


def download_dump(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            shutil.copyfileobj(resp.raw, fh)
    return dest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Import ClinicalTrials.gov bulk dump into pharma tables")
    parser.add_argument("--zip", dest="zip_path", help="Path to AllPublicXML.zip (will download if missing)")
    parser.add_argument("--url", default=DEFAULT_DUMP_URL, help="Override ClinicalTrials.gov dump URL")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("ops/data/pharma_sponsor_map.json"),
        help="JSON mapping of tickers to sponsor/intervention aliases",
    )
    args = parser.parse_args(argv)

    zip_path = Path(args.zip_path) if args.zip_path else DEFAULT_DATA_DIR / "AllPublicXML.zip"
    if not zip_path.exists():
        print(f"Downloading ClinicalTrials.gov archive to {zip_path}…", file=sys.stderr)
        download_dump(args.url, zip_path)

    mapping = load_sponsor_map(args.mapping)
    if not mapping:
        print("No sponsor mappings found; aborting.", file=sys.stderr)
        raise SystemExit(1)

    print("Parsing dump…", file=sys.stderr)
    per_ticker = parse_dump(zip_path, mapping)
    print(f"Matched {sum(len(v) for v in per_ticker.values())} studies across {len(per_ticker)} tickers.")

    if not per_ticker:
        print("Nothing to ingest.")
        return

    session: Session = SessionLocal()
    try:
        ingest_dump(session, per_ticker)
    finally:
        session.close()


if __name__ == "__main__":
    main()
