"""Recompute derived metrics for companies/years with fundamentals.

What this job does
------------------
Transforms raw `financials_annual` rows into `metrics_annual` per fiscal year,
precomputing values so screening is fast.

Computed fields (per fiscal year)
- cash_debt_ratio = cash_and_sti / total_debt
- rev_yoy, ni_yoy
- rev_cagr_5y, ni_cagr_5y (trailing)
- growth_consistency (count of years in last 10 where both revenue and NI grew)
- fcf = CFO - CapEx
- fcf_cagr_5y (trailing, requires positive FCF at year and year-5)
- shares_outstanding (copied from financials for convenience)
- ttm_eps (left None for now)

Usage
-----
$ python -m ops.recompute_metrics --limit 100
$ python -m ops.recompute_metrics --ticker AAPL
$ python -m ops.recompute_metrics --company-id 123
"""
from __future__ import annotations

import argparse
from typing import Dict, List, Optional

from sqlalchemy import select, insert, update
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import Company, FinancialAnnual, MetricsAnnual
from app.etl.transform_compute_metrics import build_metrics_rows


def cagr(first: float, last: float, years: int) -> float | None:
    if first is None or last is None or years <= 0:
        return None
    if first <= 0 or last <= 0:
        return None
    try:
        return (last / first) ** (1.0 / years) - 1.0
    except Exception:
        return None


def compute_company_metrics(db: Session, company_id: int) -> int:
    """Compute and upsert metrics for one company. Returns rows written."""

    # IMPORTANT: select only the columns we actually need
    rows = db.execute(
        select(
            FinancialAnnual.fiscal_year,
            FinancialAnnual.revenue,
            FinancialAnnual.net_income,
            FinancialAnnual.cash_and_sti,
            FinancialAnnual.total_debt,
            FinancialAnnual.cfo,
            FinancialAnnual.capex,
            FinancialAnnual.shares_outstanding,
        )
        .where(FinancialAnnual.company_id == company_id)
        .order_by(FinancialAnnual.fiscal_year)
    ).mappings().all()

    if not rows:
        return 0

    fiscal_years = [int(r["fiscal_year"]) for r in rows]
    revenue      = [float(r["revenue"]) if r["revenue"] is not None else None for r in rows]
    net_income   = [float(r["net_income"]) if r["net_income"] is not None else None for r in rows]
    cash_and_sti = [float(r["cash_and_sti"]) if r["cash_and_sti"] is not None else None for r in rows]
    total_debt   = [float(r["total_debt"]) if r["total_debt"] is not None else None for r in rows]

    # Build base metrics (cash/debt, YoY, CAGRs, growth_consistency, etc.)
    metric_rows = build_metrics_rows(
        fiscal_years=fiscal_years,
        revenue=revenue,
        net_income=net_income,
        cash_and_sti=cash_and_sti,
        total_debt=total_debt,
        ttm_eps=None,  # populate later if you add quarterly TTM logic
    )

    # --- FCF & 5y trailing CAGR ---
    # Compute FCF (= cfo - capex) per year and store in dict keyed by year
    fcf_by_year: Dict[int, Optional[float]] = {}
    shares_by_year: Dict[int, Optional[float]] = {}
    for r in rows:
        fy = int(r["fiscal_year"])
        cfo = float(r["cfo"]) if r["cfo"] is not None else None
        cap = float(r["capex"]) if r["capex"] is not None else None
        sh  = float(r["shares_outstanding"]) if r["shares_outstanding"] is not None else None

        f: Optional[float] = None
        if cfo is not None and cap is not None:
            # CapEx is a cash outflow; tags we ingest are positive numbers.
            # Using CFO - CapEx is robust even if a filer reports capex as negative.
            f = cfo - cap
        fcf_by_year[fy] = f
        shares_by_year[fy] = sh

    def fcf_cagr_5y_at(year: int) -> Optional[float]:
        y0 = year - 5
        first = fcf_by_year.get(y0)
        last  = fcf_by_year.get(year)
        if first is None or last is None or first <= 0 or last <= 0:
            return None
        return cagr(first, last, 5)

    # Merge FCF fields into the metric rows by fiscal year
    by_year: Dict[int, dict] = {int(m["fiscal_year"]): m for m in metric_rows}
    for fy in fiscal_years:
        m = by_year.get(fy)
        if not m:
            continue
        m["fcf"] = fcf_by_year.get(fy)
        m["fcf_cagr_5y"] = fcf_cagr_5y_at(fy)
        m["shares_outstanding"] = shares_by_year.get(fy)

    # --- Upsert to metrics_annual ---
    written = 0
    for m in metric_rows:
        fy = int(m["fiscal_year"])

        existing = db.execute(
            select(MetricsAnnual).where(
                (MetricsAnnual.company_id == company_id)
                & (MetricsAnnual.fiscal_year == fy)
            )
        ).scalar_one_or_none()

        values = {
            "cash_debt_ratio": m.get("cash_debt_ratio"),
            "rev_yoy": m.get("rev_yoy"),
            "ni_yoy": m.get("ni_yoy"),
            "rev_cagr_5y": m.get("rev_cagr_5y"),
            "ni_cagr_5y": m.get("ni_cagr_5y"),
            "growth_consistency": m.get("growth_consistency"),
            "ttm_eps": m.get("ttm_eps"),
            "fcf": m.get("fcf"),
            "fcf_cagr_5y": m.get("fcf_cagr_5y"),
            "shares_outstanding": m.get("shares_outstanding"),
        }

        if existing is None:
            db.execute(insert(MetricsAnnual).values(company_id=company_id, fiscal_year=fy, **values))
        else:
            db.execute(
                update(MetricsAnnual)
                .where(
                    (MetricsAnnual.company_id == company_id)
                    & (MetricsAnnual.fiscal_year == fy)
                )
                .values(**values)
            )
        written += 1

    db.commit()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute derived metrics")
    parser.add_argument("--limit", type=int, default=200, help="Max companies to process")
    parser.add_argument("--ticker", type=str, default=None, help="Only this ticker (exact)")
    parser.add_argument("--company-id", type=int, default=None, help="Only this company_id")
    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        q = select(Company).where(Company.is_tracked == True)
        if args.ticker:
            q = q.where(Company.ticker == args.ticker.upper())
        if args.company_id:
            q = q.where(Company.id == args.company_id)
        q = q.order_by(Company.ticker).limit(args.limit)

        companies = db.scalars(q).all()
        total = 0
        for co in companies:
            n = compute_company_metrics(db, co.id)
            print(f"[watchTower] {co.ticker}: metrics rows written={n}")
            total += n
        print(f"[watchTower] Done. Total metrics rows written: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
