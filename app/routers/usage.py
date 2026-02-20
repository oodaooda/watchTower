from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import LLMModelPrice, LLMUsageEvent
from app.core.schemas import (
    LLMModelPriceIn,
    LLMModelPriceOut,
    UsageBucketOut,
    UsageModelBreakdownOut,
    UsageSummaryOut,
)

router = APIRouter(prefix="/usage", tags=["usage"])

Granularity = Literal["hour", "day", "week", "month", "year"]


def _require_admin(authorization: str | None):
    token = settings.admin_settings_token
    if not token:
        raise HTTPException(status_code=503, detail="Settings admin token not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if authorization.replace("Bearer ", "", 1).strip() != token:
        raise HTTPException(status_code=403, detail="Invalid token")


def _default_lookback(granularity: Granularity) -> int:
    return {
        "hour": 48,
        "day": 30,
        "week": 12,
        "month": 12,
        "year": 5,
    }[granularity]


def _window_start(granularity: Granularity, lookback: int) -> datetime:
    now = datetime.now(timezone.utc)
    if granularity == "hour":
        return now - timedelta(hours=lookback)
    if granularity == "day":
        return now - timedelta(days=lookback)
    if granularity == "week":
        return now - timedelta(weeks=lookback)
    if granularity == "month":
        return now - timedelta(days=30 * lookback)
    return now - timedelta(days=365 * lookback)


def _price_map(db: Session) -> dict[tuple[str, str], tuple[float, float, float]]:
    rows = db.execute(
        select(LLMModelPrice).where(LLMModelPrice.active.is_(True))
    ).scalars().all()
    out: dict[tuple[str, str], tuple[float, float, float]] = {}
    for row in rows:
        out[(row.provider, row.model)] = (
            float(row.input_per_million or 0),
            float(row.output_per_million or 0),
            float(row.cache_read_per_million or 0),
        )
    return out


def _cost_for_row(
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int,
    rates: tuple[float, float, float],
) -> float:
    in_rate, out_rate, cache_rate = rates
    return (
        (float(input_tokens) / 1_000_000.0) * in_rate
        + (float(output_tokens) / 1_000_000.0) * out_rate
        + (float(cached_input_tokens) / 1_000_000.0) * cache_rate
    )


@router.get("/prices", response_model=list[LLMModelPriceOut])
def list_prices(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)
    rows = db.execute(
        select(LLMModelPrice).order_by(LLMModelPrice.provider.asc(), LLMModelPrice.model.asc())
    ).scalars().all()
    return [LLMModelPriceOut.model_validate(r) for r in rows]


@router.put("/prices", response_model=LLMModelPriceOut)
def upsert_price(
    payload: LLMModelPriceIn,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)
    row = db.execute(
        select(LLMModelPrice).where(
            LLMModelPrice.provider == payload.provider,
            LLMModelPrice.model == payload.model,
        )
    ).scalar_one_or_none()
    if row is None:
        row = LLMModelPrice(provider=payload.provider, model=payload.model)
        db.add(row)
    row.input_per_million = Decimal(str(payload.input_per_million))
    row.output_per_million = Decimal(str(payload.output_per_million))
    row.cache_read_per_million = Decimal(str(payload.cache_read_per_million))
    row.active = payload.active
    db.commit()
    db.refresh(row)
    return LLMModelPriceOut.model_validate(row)


@router.get("/summary", response_model=UsageSummaryOut)
def usage_summary(
    granularity: Granularity = Query(default="day"),
    lookback: int | None = Query(default=None, ge=1, le=3650),
    model: str | None = Query(default=None),
    provider: str = Query(default="openai"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_admin(authorization)

    lookback_value = lookback if lookback is not None else _default_lookback(granularity)
    start_at = start.astimezone(timezone.utc) if start else _window_start(granularity, lookback_value)
    end_at = end.astimezone(timezone.utc) if end else datetime.now(timezone.utc)
    if end_at <= start_at:
        raise HTTPException(status_code=400, detail="end must be greater than start")

    tz_safe = (settings.timezone or "UTC").replace("'", "''")
    bucket_expr = func.date_trunc(
        literal_column(f"'{granularity}'"),
        func.timezone(literal_column(f"'{tz_safe}'"), LLMUsageEvent.created_at),
    )

    stmt = (
        select(
            bucket_expr.label("bucket"),
            LLMUsageEvent.provider,
            LLMUsageEvent.model,
            func.count(LLMUsageEvent.id).label("requests"),
            func.coalesce(func.sum(LLMUsageEvent.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LLMUsageEvent.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(LLMUsageEvent.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(LLMUsageEvent.cached_input_tokens), 0).label("cached_input_tokens"),
        )
        .where(
            LLMUsageEvent.created_at >= start_at,
            LLMUsageEvent.created_at < end_at,
            LLMUsageEvent.provider == provider,
        )
    )
    if model:
        stmt = stmt.where(LLMUsageEvent.model == model)

    rows = db.execute(
        stmt.group_by(bucket_expr, LLMUsageEvent.provider, LLMUsageEvent.model).order_by(bucket_expr.asc())
    ).all()

    prices = _price_map(db)

    bucket_totals: dict[str, UsageBucketOut] = {}
    model_totals: dict[tuple[str, str], UsageModelBreakdownOut] = {}
    grand = UsageBucketOut(
        bucket="total",
        requests=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        cached_input_tokens=0,
        cost=0.0,
    )

    for bucket, row_provider, row_model, requests, input_tokens, output_tokens, total_tokens, cached_input_tokens in rows:
        key = (str(row_provider), str(row_model))
        rates = prices.get(key, (0.0, 0.0, 0.0))
        cost = _cost_for_row(int(input_tokens), int(output_tokens), int(cached_input_tokens), rates)
        bucket_key = bucket.isoformat() if hasattr(bucket, "isoformat") else str(bucket)

        if bucket_key not in bucket_totals:
            bucket_totals[bucket_key] = UsageBucketOut(
                bucket=bucket_key,
                requests=0,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cached_input_tokens=0,
                cost=0.0,
            )
        b = bucket_totals[bucket_key]
        b.requests += int(requests)
        b.input_tokens += int(input_tokens)
        b.output_tokens += int(output_tokens)
        b.total_tokens += int(total_tokens)
        b.cached_input_tokens += int(cached_input_tokens)
        b.cost = round(float(b.cost) + float(cost), 6)

        if key not in model_totals:
            model_totals[key] = UsageModelBreakdownOut(
                provider=key[0],
                model=key[1],
                requests=0,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cached_input_tokens=0,
                cost=0.0,
            )
        m = model_totals[key]
        m.requests += int(requests)
        m.input_tokens += int(input_tokens)
        m.output_tokens += int(output_tokens)
        m.total_tokens += int(total_tokens)
        m.cached_input_tokens += int(cached_input_tokens)
        m.cost = round(float(m.cost) + float(cost), 6)

        grand.requests += int(requests)
        grand.input_tokens += int(input_tokens)
        grand.output_tokens += int(output_tokens)
        grand.total_tokens += int(total_tokens)
        grand.cached_input_tokens += int(cached_input_tokens)
        grand.cost = round(float(grand.cost) + float(cost), 6)

    buckets = sorted(bucket_totals.values(), key=lambda x: x.bucket)
    by_model = sorted(model_totals.values(), key=lambda x: (x.cost, x.total_tokens), reverse=True)

    return UsageSummaryOut(
        granularity=granularity,
        start=start_at.isoformat(),
        end=end_at.isoformat(),
        totals=grand,
        buckets=buckets,
        by_model=by_model,
    )
