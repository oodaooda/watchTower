from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any

from app.core.config import settings
from app.services.signals.fetcher import get_json
from app.services.signals.types import SignalObservation

MODULE_ID = "M1"
SERIES_ID = "BAMLH0A0HYM2"
METRIC = "hy_oas_bps"
SOURCE = "FRED"


def fred_observations_url(api_key: str) -> str:
    return (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={SERIES_ID}&api_key={api_key}&file_type=json"
        "&sort_order=desc&limit=10"
    )


def status_for_hy_oas_bps(value: float) -> str:
    if value > 450:
        return "red"
    if value >= 350:
        return "amber"
    return "green"


def transform_fred_hy_oas(payload: dict[str, Any]) -> list[SignalObservation]:
    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise ValueError("FRED payload missing observations list")

    rows: list[SignalObservation] = []
    for item in observations:
        if not isinstance(item, dict):
            continue
        raw_value = item.get("value")
        raw_date = item.get("date")
        if raw_value in (None, ".") or not raw_date:
            continue
        try:
            value_pct = float(raw_value)
            day = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
        except ValueError:
            continue
        value_bps = value_pct * 100.0
        rows.append(
            SignalObservation(
                ts=datetime.combine(day, time.min, tzinfo=timezone.utc),
                module_id=MODULE_ID,
                entity="",
                metric=METRIC,
                value=value_bps,
                status=status_for_hy_oas_bps(value_bps),
                source=SOURCE,
                raw_payload={
                    "series_id": SERIES_ID,
                    "date": raw_date,
                    "value": raw_value,
                    "units": "percent",
                },
            )
        )
    rows.sort(key=lambda row: row.ts)
    return rows


def fetch_observations() -> list[SignalObservation]:
    if not settings.fred_api_key:
        raise RuntimeError("FRED_API_KEY not configured")
    return transform_fred_hy_oas(get_json(fred_observations_url(settings.fred_api_key)))
