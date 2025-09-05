"""Create database tables for watchTower.

This script imports the ORM models and calls `Base.metadata.create_all()` on the
configured DATABASE_URL. Run it once during setup (and after model changes if
you're not using migrations yet).

Usage
-----
$ python -m ops.create_tables

Notes
-----
- Uses SQLAlchemy's `create_all` which is idempotent (creates missing tables; no
  destructive changes). For production, consider Alembic migrations.
- Reads connection info from env via `Settings` (see `.env.example`).
"""
from __future__ import annotations

from app.core.db import engine, Base  # engine is built from env in app.core.config
# Import models so SQLAlchemy knows about them before create_all()
from app.core import models  # noqa: F401  (imported for side effects)


def main() -> None:
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
    print("[watchTower] Tables created (or already exist).")

if __name__ == "__main__":
    main()
