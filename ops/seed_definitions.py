"""Seed the glossary `definitions` table with core financial terms.

This script inserts/updates Markdown explanations for key metrics used by
watchTower. The frontend can render these directly on a Definitions page.

Usage
-----
$ python -m ops.seed_definitions
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import Definition

SEED = [
    (
        "piotroski_f",
        "Piotroski F-Score",
        (
            "A 0–9 score across profitability, leverage/liquidity, and operating\n"
            "efficiency (nine binary tests). Higher is better.\n\n"
            "Tests: profit_pos, cfo_pos, roa_improve, accruals_good, leverage_down,\n"
            "liquidity_up, no_dilution, margin_up, asset_turnover_up."
        ),
    ),
    (
        "altman_z",
        "Altman Z-Score",
        (
            "Distress score using five ratios (public manufacturing formula):\\n\n"
            "Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5, where\\n\n"
            "X1=WC/Assets, X2=RE/Assets, X3=EBIT/Assets, X4=MV Equity/Liabilities, X5=Sales/Assets."
        ),
    ),
    (
        "roic",
        "Return on Invested Capital (ROIC)",
        "After-tax operating profit divided by invested capital; proxy for value creation.",
    ),
    (
        "fcf",
        "Free Cash Flow (FCF)",
        "Cash from operations minus capital expenditures.",
    ),
    (
        "cagr",
        "Compound Annual Growth Rate (CAGR)",
        "((End / Start)^(1/n)) − 1 over n years; measures smoothed growth.",
    ),
    (
        "debt_ebitda",
        "Debt/EBITDA",
        "Leverage ratio: total debt divided by EBITDA.",
    ),
    (
        "interest_coverage",
        "Interest Coverage",
        "EBIT (or operating income) divided by interest expense.",
    ),
    (
        "ttm_eps",
        "Earnings Per Share (TTM)",
        "Trailing twelve months earnings divided by diluted weighted shares.",
    ),
]


def upsert_definitions(db: Session, items) -> None:
    for key, title, body_md in items:
        row = db.get(Definition, key)
        if row is None:
            db.add(Definition(key=key, title=title, body_md=body_md))
        else:
            row.title = title
            row.body_md = body_md


def main() -> None:
    db: Session = SessionLocal()
    try:
        upsert_definitions(db, SEED)
        db.commit()
        print(f"[watchTower] Seeded {len(SEED)} definitions.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
