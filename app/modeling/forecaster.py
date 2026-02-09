from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


PERIOD_ORDER = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
ORDER_PERIOD = {v: k for k, v in PERIOD_ORDER.items()}


@dataclass
class Assumptions:
    scenario: str
    revenue_cagr_start: float
    revenue_cagr_floor: float
    revenue_decay_quarters: int
    gross_margin_target: float
    gross_margin_glide_quarters: int
    rnd_pct: float
    sm_pct: float
    ga_pct: float
    tax_rate: float
    interest_pct_revenue: float
    dilution_pct_annual: float
    seasonality_mode: str
    driver_blend_start_weight: float
    driver_blend_end_weight: float
    driver_blend_ramp_quarters: int


@dataclass
class KPI:
    fiscal_year: int
    fiscal_period: str
    mau: Optional[float] = None
    dau: Optional[float] = None
    paid_subs: Optional[float] = None
    paid_conversion_pct: Optional[float] = None
    arpu: Optional[float] = None
    churn_pct: Optional[float] = None


def _period_key(year: int, period: str) -> Tuple[int, int]:
    return (year, PERIOD_ORDER.get(period, 0))


def _next_period(year: int, period: str) -> Tuple[int, str]:
    idx = PERIOD_ORDER.get(period, 4)
    if idx >= 4:
        return (year + 1, "Q1")
    return (year, ORDER_PERIOD[idx + 1])


def _quarterly_growth_from_cagr(cagr: float) -> float:
    return (1 + cagr) ** 0.25 - 1


def _linear_glide(start: float, end: float, step: int, total_steps: int) -> float:
    if total_steps <= 0:
        return end
    t = min(max(step, 0), total_steps) / total_steps
    return start + (end - start) * t


def _seasonality_indices(revenues: List[Tuple[str, float]]) -> Optional[Dict[str, float]]:
    if len(revenues) < 8:
        return None
    by_period: Dict[str, List[float]] = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
    for period, value in revenues:
        if period in by_period and value is not None:
            by_period[period].append(value)
    if any(len(vals) < 2 for vals in by_period.values()):
        return None
    avg_total = sum(sum(vals) for vals in by_period.values())
    count_total = sum(len(vals) for vals in by_period.values())
    if count_total == 0:
        return None
    overall_avg = avg_total / count_total
    if overall_avg <= 0:
        return None
    return {p: (sum(vals) / len(vals)) / overall_avg for p, vals in by_period.items()}


def _apply_seasonality(quarters: List[Dict[str, float]], indices: Dict[str, float]) -> None:
    if not indices:
        return
    by_year: Dict[int, List[Dict[str, float]]] = {}
    for row in quarters:
        by_year.setdefault(row["fiscal_year"], []).append(row)

    for year_rows in by_year.values():
        base_total = sum(r["revenue"] for r in year_rows)
        if base_total <= 0:
            continue
        adjusted = []
        for r in year_rows:
            idx = indices.get(r["fiscal_period"], 1.0)
            adjusted.append(r["revenue"] * idx)
        adj_total = sum(adjusted)
        if adj_total <= 0:
            continue
        scale = base_total / adj_total
        for r, adj in zip(year_rows, adjusted):
            r["revenue"] = adj * scale


def _project_kpis(
    known: Dict[Tuple[int, int], KPI], start_year: int, start_period: str, horizon: int
) -> Dict[Tuple[int, int], KPI]:
    ordered_keys = sorted(known.keys())
    if not ordered_keys:
        return {}
    values_by_metric: Dict[str, List[float]] = {"mau": [], "dau": [], "arpu": [], "paid_subs": []}
    for key in ordered_keys[-4:]:
        kpi = known[key]
        for metric in values_by_metric:
            val = getattr(kpi, metric)
            if val is not None:
                values_by_metric[metric].append(val)
    growth_rates: Dict[str, float] = {}
    for metric, series in values_by_metric.items():
        if len(series) >= 2 and series[0] > 0:
            growth_rates[metric] = (series[-1] / series[0]) ** (1 / max(len(series) - 1, 1)) - 1
        else:
            growth_rates[metric] = 0.0

    projected: Dict[Tuple[int, int], KPI] = dict(known)
    last_key = ordered_keys[-1]
    last_kpi = known[last_key]
    year = start_year
    period = start_period
    for _ in range(horizon):
        key = _period_key(year, period)
        if key in projected:
            year, period = _next_period(year, period)
            continue
        next_kpi = KPI(fiscal_year=year, fiscal_period=period)
        for metric, gr in growth_rates.items():
            last_val = getattr(last_kpi, metric)
            if last_val is None:
                continue
            setattr(next_kpi, metric, last_val * (1 + gr))
        next_kpi.paid_conversion_pct = last_kpi.paid_conversion_pct
        next_kpi.churn_pct = last_kpi.churn_pct
        projected[key] = next_kpi
        last_kpi = next_kpi
        year, period = _next_period(year, period)
    return projected


def generate_forecast(
    assumptions: Assumptions,
    historical_quarters: List[Dict[str, Optional[float]]],
    kpis: List[KPI],
    horizon_quarters: int,
) -> List[Dict[str, Optional[float]]]:
    if not historical_quarters:
        return []

    sorted_hist = sorted(
        historical_quarters,
        key=lambda r: _period_key(r["fiscal_year"], r["fiscal_period"]),
    )
    last = sorted_hist[-1]
    last_revenue = last.get("revenue") or 0.0
    last_shares = last.get("shares_outstanding") or 0.0

    gross_margin_last = None
    if last.get("gross_profit") is not None and last.get("revenue"):
        gross_margin_last = float(last["gross_profit"]) / float(last["revenue"])
    gross_margin_start = gross_margin_last if gross_margin_last is not None else assumptions.gross_margin_target

    rnd_pct = assumptions.rnd_pct or 0.0
    sm_pct = assumptions.sm_pct or 0.0
    ga_pct = assumptions.ga_pct or 0.0

    kpi_map = {_period_key(k.fiscal_year, k.fiscal_period): k for k in kpis}
    projected_kpis = _project_kpis(
        kpi_map, last["fiscal_year"], last["fiscal_period"], horizon_quarters
    )

    seasonal_indices = None
    if assumptions.seasonality_mode == "auto":
        seasonal_indices = _seasonality_indices(
            [(r["fiscal_period"], float(r["revenue"])) for r in sorted_hist if r.get("revenue")]
        )

    quarters: List[Dict[str, Optional[float]]] = []
    year, period = _next_period(last["fiscal_year"], last["fiscal_period"])
    base_revenue = float(last_revenue)
    share_count = float(last_shares)
    dilution_q = _quarterly_growth_from_cagr(assumptions.dilution_pct_annual or 0.0)

    for idx in range(horizon_quarters):
        annual_growth = _linear_glide(
            assumptions.revenue_cagr_start,
            assumptions.revenue_cagr_floor,
            idx,
            assumptions.revenue_decay_quarters,
        )
        q_growth = _quarterly_growth_from_cagr(annual_growth)
        base_revenue = base_revenue * (1 + q_growth)

        gross_margin = _linear_glide(
            gross_margin_start,
            assumptions.gross_margin_target,
            idx,
            assumptions.gross_margin_glide_quarters,
        )

        driver_revenue = None
        key = _period_key(year, period)
        kpi = projected_kpis.get(key)
        if kpi and kpi.dau and kpi.paid_conversion_pct and kpi.arpu:
            driver_revenue = kpi.dau * kpi.paid_conversion_pct * kpi.arpu

        blend_weight = _linear_glide(
            assumptions.driver_blend_start_weight,
            assumptions.driver_blend_end_weight,
            idx,
            assumptions.driver_blend_ramp_quarters,
        )
        if driver_revenue is None:
            blend_weight = 0.0
        revenue = base_revenue if driver_revenue is None else (
            blend_weight * driver_revenue + (1 - blend_weight) * base_revenue
        )

        cogs = revenue * (1 - gross_margin)
        gross_profit = revenue - cogs
        rnd = revenue * rnd_pct
        sm = revenue * sm_pct
        ga = revenue * ga_pct
        operating_expenses = rnd + sm + ga
        operating_income = gross_profit - operating_expenses
        interest = revenue * (assumptions.interest_pct_revenue or 0.0)
        pretax = operating_income - interest
        tax = max(pretax, 0) * (assumptions.tax_rate or 0.0)
        net_income = pretax - tax

        share_count = share_count * (1 + dilution_q) if share_count else 0.0
        eps = net_income / share_count if share_count else None

        quarters.append(
            {
                "fiscal_year": year,
                "fiscal_period": period,
                "revenue": revenue,
                "cost_of_revenue": cogs,
                "gross_profit": gross_profit,
                "research_and_development": rnd,
                "sales_and_marketing": sm,
                "general_and_administrative": ga,
                "operating_expenses": operating_expenses,
                "operating_income": operating_income,
                "interest_expense": interest,
                "pretax_income": pretax,
                "income_tax_expense": tax,
                "net_income": net_income,
                "shares_outstanding": share_count,
                "eps": eps,
                "driver_revenue": driver_revenue,
                "baseline_revenue": base_revenue,
                "blend_weight": blend_weight,
            }
        )
        year, period = _next_period(year, period)

    if seasonal_indices:
        _apply_seasonality(quarters, seasonal_indices)

    history_map = {(r["fiscal_year"], r["fiscal_period"]): r for r in sorted_hist}
    for row in quarters:
        prev = history_map.get((row["fiscal_year"] - 1, row["fiscal_period"]))
        if prev and prev.get("revenue"):
            row["revenue_yoy_pct"] = (row["revenue"] / prev["revenue"]) - 1
        if row.get("revenue"):
            row["gross_margin_pct"] = row["gross_profit"] / row["revenue"]
            row["operating_margin_pct"] = row["operating_income"] / row["revenue"]
            row["net_margin_pct"] = row["net_income"] / row["revenue"]
        history_map[(row["fiscal_year"], row["fiscal_period"])] = row

    return quarters


def rollup_annual(quarters: Iterable[Dict[str, Optional[float]]]) -> List[Dict[str, Optional[float]]]:
    yearly: Dict[int, Dict[str, Optional[float]]] = {}
    for row in quarters:
        year = row["fiscal_year"]
        bucket = yearly.setdefault(
            year,
            {
                "fiscal_year": year,
                "revenue": 0.0,
                "cost_of_revenue": 0.0,
                "gross_profit": 0.0,
                "research_and_development": 0.0,
                "sales_and_marketing": 0.0,
                "general_and_administrative": 0.0,
                "operating_expenses": 0.0,
                "operating_income": 0.0,
                "interest_expense": 0.0,
                "pretax_income": 0.0,
                "income_tax_expense": 0.0,
                "net_income": 0.0,
                "shares_outstanding": 0.0,
                "eps": None,
                "quarters": 0,
            },
        )
        for key in (
            "revenue",
            "cost_of_revenue",
            "gross_profit",
            "research_and_development",
            "sales_and_marketing",
            "general_and_administrative",
            "operating_expenses",
            "operating_income",
            "interest_expense",
            "pretax_income",
            "income_tax_expense",
            "net_income",
        ):
            val = row.get(key)
            if val is not None:
                bucket[key] = float(bucket[key]) + float(val)
        shares = row.get("shares_outstanding")
        if shares is not None:
            bucket["shares_outstanding"] = float(bucket["shares_outstanding"]) + float(shares)
        bucket["quarters"] = int(bucket["quarters"]) + 1

    annual_rows: List[Dict[str, Optional[float]]] = []
    for year in sorted(yearly.keys()):
        bucket = yearly[year]
        count = int(bucket.pop("quarters", 0) or 0)
        if count > 0:
            bucket["shares_outstanding"] = float(bucket["shares_outstanding"]) / count
        if bucket.get("shares_outstanding"):
            bucket["eps"] = bucket["net_income"] / bucket["shares_outstanding"]
        if bucket.get("revenue"):
            bucket["gross_margin_pct"] = bucket["gross_profit"] / bucket["revenue"]
            bucket["operating_margin_pct"] = bucket["operating_income"] / bucket["revenue"]
            bucket["net_margin_pct"] = bucket["net_income"] / bucket["revenue"]
        annual_rows.append(bucket)

    for idx, row in enumerate(annual_rows):
        if idx == 0:
            continue
        prev = annual_rows[idx - 1]
        if prev.get("revenue"):
            row["revenue_yoy_pct"] = row["revenue"] / prev["revenue"] - 1

    return annual_rows
