from datetime import datetime

from app.routers.prices import _build_change_summary, _slice_daily


def test_slice_daily_supports_three_month_range():
    points = [
        (datetime(2025, 12, 1), 100.0),
        (datetime(2026, 1, 15), 110.0),
        (datetime(2026, 2, 15), 120.0),
        (datetime(2026, 3, 15), 130.0),
    ]

    sliced = _slice_daily(points, "3m")
    assert len(sliced) == 3
    assert sliced[0][0] == datetime(2026, 1, 15)


def test_build_change_summary_reports_day_month_year_changes():
    points = [
        (datetime(2025, 3, 1), 100.0),
        (datetime(2026, 2, 1), 120.0),
        (datetime(2026, 3, 1), 140.0),
        (datetime(2026, 3, 2), 150.0),
    ]

    summary = _build_change_summary(points)
    assert summary["1d"]["change"] == 10.0
    assert summary["1m"]["change"] == 30.0
    assert summary["1y"]["change"] == 50.0
