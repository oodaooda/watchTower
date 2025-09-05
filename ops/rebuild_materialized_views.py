"""Refresh materialized views (placeholder).

If you choose to create Postgres materialized views (e.g., for faster screens
or latest-year snapshots), put their refresh logic here.

Example views you might add later:
- `mv_latest_metrics` — latest fiscal-year metrics per company
- `mv_screen_grid`   — denormalized join for the screener results grid

Usage
-----
$ python -m ops.rebuild_materialized_views
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal


VIEWS = [
    # ("mv_latest_metrics", "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_metrics"),
    # ("mv_screen_grid", "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_screen_grid"),
]


def main() -> None:
    db: Session = SessionLocal()
    try:
        for name, sql in VIEWS:
            print(f"[watchTower] Refreshing {name}...")
            db.execute(text(sql))
        db.commit()
        print("[watchTower] Materialized views refreshed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
