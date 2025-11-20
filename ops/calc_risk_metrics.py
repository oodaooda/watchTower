"""Compute alpha/beta risk metrics for tracked companies.

This job fetches daily adjusted closes for a company and benchmark (default SPY),
computes daily returns, runs a simple CAPM regression to obtain beta and alpha,
then stores the annualized alpha plus metadata in `company_risk_metrics`.
"""
from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.models import Company, CompanyRiskMetric
from app.etl.alpha_fetch_prices import fetch_daily_adjusted

DEFAULT_BENCHMARK = "SPY"
DEFAULT_LOOKBACK_DAYS = 756  # ~3 years of trading days
TRADING_DAYS_PER_YEAR = 252


def compute_alpha_beta(
    stock_df: pd.DataFrame,
    bench_df: pd.DataFrame,
    lookback_days: int,
    risk_free_rate: float,
) -> tuple[Optional[float], Optional[float], Optional[float], int]:
    """Return (beta, alpha_daily, alpha_annualized, data_points)."""
    if stock_df is None or bench_df is None:
        return None, None, None, 0

    df = stock_df.merge(bench_df, on="date", suffixes=("_stock", "_bench"))
    if df.empty:
        return None, None, 0
    df = df.sort_values("date").tail(lookback_days + 1)
    df["ret_stock"] = df["adj_close_stock"].pct_change()
    df["ret_bench"] = df["adj_close_bench"].pct_change()
    df = df.dropna(subset=["ret_stock", "ret_bench"])
    if df.empty:
        return None, None, None, 0

    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    df["excess_stock"] = df["ret_stock"] - rf_daily
    df["excess_bench"] = df["ret_bench"] - rf_daily

    var_x = df["excess_bench"].var()
    if not var_x or math.isclose(var_x, 0.0):
        return None, None, None, len(df)

    cov_xy = df["excess_stock"].cov(df["excess_bench"])
    beta = cov_xy / var_x

    mean_x = df["excess_bench"].mean()
    mean_y = df["excess_stock"].mean()
    alpha_daily = mean_y - beta * mean_x
    alpha_annual = (1 + alpha_daily) ** TRADING_DAYS_PER_YEAR - 1
    return float(beta), float(alpha_daily), float(alpha_annual), len(df)


def upsert_metric(
    db,
    company: Company,
    beta: Optional[float],
    alpha_daily: Optional[float],
    alpha_annual: Optional[float],
    benchmark: str,
    risk_free_rate: float,
    lookback_days: int,
    data_points: int,
):
    metric = db.query(CompanyRiskMetric).filter(CompanyRiskMetric.company_id == company.id).one_or_none()
    now = datetime.now(timezone.utc)
    if metric:
        metric.beta = beta
        metric.alpha = alpha_daily
        metric.alpha_annual = alpha_annual
        metric.benchmark = benchmark
        metric.risk_free_rate = risk_free_rate
        metric.lookback_days = lookback_days
        metric.data_points = data_points
        metric.computed_at = now
    else:
        metric = CompanyRiskMetric(
            company_id=company.id,
            beta=beta,
            alpha=alpha_daily,
            alpha_annual=alpha_annual,
            benchmark=benchmark,
            risk_free_rate=risk_free_rate,
            lookback_days=lookback_days,
            data_points=data_points,
            computed_at=now,
        )
        db.add(metric)
    db.commit()


def process_company(db, company: Company, benchmark: str, lookback_days: int, risk_free_rate: float, quiet: bool):
    stock_df = fetch_daily_adjusted(company.ticker)
    bench_df = fetch_daily_adjusted(benchmark)
    beta, alpha_daily, alpha_annual, data_points = compute_alpha_beta(
        stock_df, bench_df, lookback_days, risk_free_rate
    )
    upsert_metric(db, company, beta, alpha_daily, alpha_annual, benchmark, risk_free_rate, lookback_days, data_points)
    if not quiet:
        print(
            f"[risk] {company.ticker}: beta={beta if beta is not None else '—'} "
            f"alpha={alpha_annual if alpha_annual is not None else '—'} "
            f"points={data_points}"
        )


def main():
    parser = argparse.ArgumentParser(description="Compute/store alpha/beta risk metrics.")
    parser.add_argument("--ticker", nargs="*", help="Specific tickers to process (default: all tracked).")
    parser.add_argument("--benchmark", default=DEFAULT_BENCHMARK, help="Benchmark ticker (default: SPY).")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--risk-free-rate", type=float, default=0.02, help="Annual risk-free rate (e.g., 0.02 for 2%).")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not settings.alpha_vantage_api_key:
        raise SystemExit("ALPHA_VANTAGE_API_KEY not configured.")

    db = SessionLocal()
    try:
        if args.ticker:
            companies = (
                db.query(Company)
                .filter(Company.ticker.in_([t.upper() for t in args.ticker]))
                .all()
            )
        else:
            companies = db.query(Company).filter(Company.is_tracked.is_(True)).all()

        for co in companies:
            process_company(db, co, args.benchmark, args.lookback_days, args.risk_free_rate, args.quiet)
    finally:
        db.close()


if __name__ == "__main__":
    main()
