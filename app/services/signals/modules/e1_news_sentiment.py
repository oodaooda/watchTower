from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.services.signals.fetcher import get_json
from app.services.signals.types import SignalObservation

MODULE_ID = "E1"
METRIC = "news_sentiment_top5"
SOURCE = "Alpha Vantage"
DEFAULT_TICKERS = ["VGT", "NVDA", "MSFT", "AAPL", "AVGO", "GOOGL", "META"]


def alpha_news_url(api_key: str, tickers: list[str] | None = None) -> str:
    ticker_list = ",".join(tickers or DEFAULT_TICKERS)
    return (
        "https://www.alphavantage.co/query"
        f"?function=NEWS_SENTIMENT&tickers={ticker_list}&sort=LATEST&limit=50&apikey={api_key}"
    )


def _parse_alpha_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def status_for_sentiment(value: float) -> str:
    if value <= -0.25:
        return "red"
    if abs(value) >= 0.15:
        return "amber"
    return "green"


def transform_news_sentiment(payload: dict[str, Any]) -> list[SignalObservation]:
    feed = payload.get("feed")
    if not isinstance(feed, list):
        raise ValueError("Alpha Vantage payload missing feed list")

    scored: list[tuple[float, dict[str, Any]]] = []
    for item in feed:
        if not isinstance(item, dict):
            continue
        try:
            score = float(item.get("overall_sentiment_score"))
        except (TypeError, ValueError):
            continue
        scored.append((abs(score), item))

    top = [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:5]]
    if not top:
        return []
    avg_score = sum(float(item.get("overall_sentiment_score", 0.0)) for item in top) / len(top)
    latest_ts = max(_parse_alpha_time(item.get("time_published")) for item in top)
    return [
        SignalObservation(
            ts=latest_ts,
            module_id=MODULE_ID,
            entity="top5",
            metric=METRIC,
            value=avg_score,
            status=status_for_sentiment(avg_score),
            source=SOURCE,
            raw_payload={
                "articles": [
                    {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "source": item.get("source"),
                        "time_published": item.get("time_published"),
                        "overall_sentiment_score": item.get("overall_sentiment_score"),
                        "overall_sentiment_label": item.get("overall_sentiment_label"),
                    }
                    for item in top
                ]
            },
        )
    ]


def fetch_observations() -> list[SignalObservation]:
    if not settings.alpha_vantage_api_key:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY not configured")
    combined_feed: list[dict[str, Any]] = []
    definitions: dict[str, Any] = {}
    for ticker in DEFAULT_TICKERS:
        payload = get_json(alpha_news_url(settings.alpha_vantage_api_key, [ticker]))
        if isinstance(payload, dict):
            combined_feed.extend(item for item in payload.get("feed", []) if isinstance(item, dict))
            for key in ("items", "relevance_score_definition", "sentiment_score_definition"):
                if key in payload:
                    definitions[key] = payload[key]
    return transform_news_sentiment({"feed": combined_feed, **definitions})
