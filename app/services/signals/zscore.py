from __future__ import annotations

import math


def z_score(value: float, history: list[float]) -> float | None:
    if len(history) < 2:
        return None
    mean = sum(history) / len(history)
    variance = sum((item - mean) ** 2 for item in history) / len(history)
    stddev = math.sqrt(variance)
    if stddev == 0:
        return None
    return (value - mean) / stddev
