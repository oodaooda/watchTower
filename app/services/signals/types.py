from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SignalObservation:
    ts: datetime
    module_id: str
    entity: str
    metric: str
    value: float
    status: str
    source: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class SignalRunResult:
    module_id: str
    status: str
    records_written: int
    error: str | None = None
