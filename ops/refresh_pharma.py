"""Refresh pharma pipeline data from ClinicalTrials.gov."""
from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.pharma_refresh import get_target_companies, refresh_company


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh pharma pipeline data from ClinicalTrials.gov")
    parser.add_argument("--ticker", help="Specific ticker to refresh")
    parser.add_argument("--lead", help="Override lead sponsor query (defaults to company name)")
    parser.add_argument("--condition", help="Optional condition/disease filter")
    parser.add_argument("--intervention", help="Optional intervention filter")
    parser.add_argument("--status", help="Optional overall status filter (e.g., RECRUITING)")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=None, help="Limit number of API pages")
    parser.add_argument("--all", action="store_true", help="Refresh all tracked companies (pharma filter applied unless --ticker supplied)")

    args = parser.parse_args()

    session: Session = SessionLocal()
    try:
        companies = get_target_companies(session, args.ticker, args.all)
        if not companies:
            print("No matching companies found.")
            return

        for company in companies:
            try:
                count = refresh_company(
                    session,
                    company,
                    lead=args.lead,
                    condition=args.condition,
                    intervention=args.intervention,
                    status=args.status,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                )
                print(f"{company.ticker}: refreshed {count} trials")
            except Exception as exc:
                session.rollback()
                print(f"Failed to refresh {company.ticker}: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
