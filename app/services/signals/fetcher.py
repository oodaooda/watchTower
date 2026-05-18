from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)


class SignalFetchError(RuntimeError):
    pass


def get_json(url: str, *, timeout: float = 15.0, retries: int = 2, headers: dict[str, str] | None = None) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, headers=headers) as client:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
                return payload
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            sleep_seconds = min(2.0 * (attempt + 1), 5.0)
            log.warning("signals_fetch_retry url=%s attempt=%s error=%s", url, attempt + 1, exc)
            time.sleep(sleep_seconds)
    raise SignalFetchError(str(last_error) if last_error else "request failed")
