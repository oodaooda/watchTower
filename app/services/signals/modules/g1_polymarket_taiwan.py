from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.services.signals.fetcher import get_json
from app.services.signals.types import SignalObservation

MODULE_ID = "G1"
METRIC = "taiwan_probability_pct"
SOURCE = "Polymarket"


class PolymarketMarketNotConfigured(RuntimeError):
    pass


def polymarket_url() -> str:
    if not settings.polymarket_taiwan_market_id:
        raise PolymarketMarketNotConfigured("POLYMARKET_TAIWAN_MARKET_ID is required for G1")
    return f"https://gamma-api.polymarket.com/markets?id={settings.polymarket_taiwan_market_id}"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _market_probability(market: dict[str, Any]) -> float | None:
    outcomes = [str(item).lower() for item in _as_list(market.get("outcomes"))]
    prices = _as_list(market.get("outcomePrices"))
    if not prices:
        return None
    index = 0
    for idx, outcome in enumerate(outcomes):
        if outcome in {"yes", "true"}:
            index = idx
            break
    try:
        return float(prices[index]) * 100.0
    except (IndexError, TypeError, ValueError):
        return None


def status_for_probability(value: float) -> str:
    if value > 15:
        return "red"
    if value > 10:
        return "amber"
    return "green"


def transform_polymarket_taiwan(payload: Any) -> list[SignalObservation]:
    markets = payload if isinstance(payload, list) else payload.get("markets") if isinstance(payload, dict) else None
    if not isinstance(markets, list):
        raise ValueError("Polymarket payload missing markets list")

    candidates: list[tuple[float, dict[str, Any]]] = []
    for market in markets:
        if not isinstance(market, dict):
            continue
        probability = _market_probability(market)
        question = str(market.get("question") or market.get("title") or "").lower()
        if probability is None or "taiwan" not in question:
            continue
        candidates.append((probability, market))

    if not candidates:
        return []
    probability, market = max(candidates, key=lambda item: item[0])
    updated = market.get("updatedAt") or market.get("createdAt")
    try:
        ts = datetime.fromisoformat(str(updated).replace("Z", "+00:00")) if updated else datetime.now(timezone.utc)
    except ValueError:
        ts = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    return [
        SignalObservation(
            ts=ts,
            module_id=MODULE_ID,
            entity=str(market.get("id") or market.get("slug") or "taiwan"),
            metric=METRIC,
            value=probability,
            status=status_for_probability(probability),
            source=SOURCE,
            raw_payload={
                "id": market.get("id"),
                "slug": market.get("slug"),
                "question": market.get("question"),
                "outcomes": market.get("outcomes"),
                "outcomePrices": market.get("outcomePrices"),
            },
        )
    ]


def fetch_observations() -> list[SignalObservation]:
    return transform_polymarket_taiwan(get_json(polymarket_url()))
