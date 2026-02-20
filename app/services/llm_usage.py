from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.db import SessionLocal
from app.core.models import LLMUsageEvent


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def extract_openai_usage(api: str, response: Any) -> Dict[str, int]:
    usage_obj = _get_attr(response, "usage", None)
    if usage_obj is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_input_tokens": 0,
        }

    if api == "responses":
        input_tokens = int(_get_attr(usage_obj, "input_tokens", 0) or 0)
        output_tokens = int(_get_attr(usage_obj, "output_tokens", 0) or 0)
        total_tokens = int(_get_attr(usage_obj, "total_tokens", input_tokens + output_tokens) or 0)
        input_details = _get_attr(usage_obj, "input_tokens_details", None)
        cached_input_tokens = int(_get_attr(input_details, "cached_tokens", 0) or 0)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cached_input_tokens": cached_input_tokens,
        }

    input_tokens = int(_get_attr(usage_obj, "prompt_tokens", 0) or 0)
    output_tokens = int(_get_attr(usage_obj, "completion_tokens", 0) or 0)
    total_tokens = int(_get_attr(usage_obj, "total_tokens", input_tokens + output_tokens) or 0)
    prompt_details = _get_attr(usage_obj, "prompt_tokens_details", None)
    cached_input_tokens = int(_get_attr(prompt_details, "cached_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_input_tokens": cached_input_tokens,
    }


def compute_usage_cost(
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int,
    input_per_million: float,
    output_per_million: float,
    cache_read_per_million: float,
) -> float:
    return (
        (float(input_tokens) / 1_000_000.0) * float(input_per_million)
        + (float(output_tokens) / 1_000_000.0) * float(output_per_million)
        + (float(cached_input_tokens) / 1_000_000.0) * float(cache_read_per_million)
    )


def record_openai_usage(
    *,
    endpoint: str,
    api: str,
    model: str,
    response: Any = None,
    success: bool = True,
    error: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> None:
    usage = extract_openai_usage(api, response)
    usage_obj = _get_attr(response, "usage", None)
    try:
        raw_usage_json = json.dumps(usage_obj, default=lambda x: getattr(x, "__dict__", str(x)))
    except Exception:
        raw_usage_json = None

    meta_payload = {"recorded_at": datetime.now(timezone.utc).isoformat()}
    if metadata:
        meta_payload.update(metadata)

    db = SessionLocal()
    try:
        db.add(
            LLMUsageEvent(
                endpoint=endpoint,
                provider="openai",
                api=api,
                model=model,
                input_tokens=int(usage["input_tokens"]),
                output_tokens=int(usage["output_tokens"]),
                total_tokens=int(usage["total_tokens"]),
                cached_input_tokens=int(usage["cached_input_tokens"]),
                success=bool(success),
                error=error,
                metadata_json=json.dumps(meta_payload),
                raw_usage_json=raw_usage_json,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
