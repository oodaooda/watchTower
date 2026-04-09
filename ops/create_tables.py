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

from sqlalchemy import inspect, text

from app.core.db import engine, Base  # engine is built from env in app.core.config
# Import models so SQLAlchemy knows about them before create_all()
from app.core import models  # noqa: F401  (imported for side effects)


def _ensure_non_destructive_columns(conn) -> None:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    if "companies" not in tables:
        company_columns = set()
    else:
        company_columns = {column["name"] for column in inspector.get_columns("companies")}

    if "asset_type" not in company_columns:
        conn.execute(text("ALTER TABLE companies ADD COLUMN asset_type VARCHAR DEFAULT 'equity'"))
        conn.execute(text("UPDATE companies SET asset_type = 'equity' WHERE asset_type IS NULL"))

    if "portfolio_positions" not in tables:
        return

    portfolio_columns = {column["name"] for column in inspector.get_columns("portfolio_positions")}
    if "entry_source" not in portfolio_columns:
        conn.execute(text("ALTER TABLE portfolio_positions ADD COLUMN entry_source VARCHAR DEFAULT 'manual'"))
        conn.execute(text("UPDATE portfolio_positions SET entry_source = 'manual' WHERE entry_source IS NULL"))

    portfolio_uniques = inspector.get_unique_constraints("portfolio_positions")
    company_unique_names = [
        constraint.get("name")
        for constraint in portfolio_uniques
        if constraint.get("column_names") == ["company_id"]
    ]

    if not company_unique_names:
        return

    dialect = conn.dialect.name
    if dialect == "sqlite":
        conn.execute(
            text(
                """
                CREATE TABLE portfolio_positions__new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    quantity NUMERIC(20, 6) NOT NULL,
                    avg_cost_basis NUMERIC(20, 6) NOT NULL,
                    entry_source VARCHAR DEFAULT 'manual' NOT NULL,
                    notes VARCHAR,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    FOREIGN KEY(company_id) REFERENCES companies (id) ON DELETE CASCADE
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO portfolio_positions__new
                    (id, company_id, quantity, avg_cost_basis, entry_source, notes, created_at, updated_at)
                SELECT id, company_id, quantity, avg_cost_basis, COALESCE(entry_source, 'manual'), notes, created_at, updated_at
                FROM portfolio_positions
                """
            )
        )
        conn.execute(text("DROP TABLE portfolio_positions"))
        conn.execute(text("ALTER TABLE portfolio_positions__new RENAME TO portfolio_positions"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_portfolio_positions_company_id ON portfolio_positions (company_id)"))
        return

    for constraint_name in company_unique_names:
        if constraint_name:
            conn.execute(text(f'ALTER TABLE portfolio_positions DROP CONSTRAINT IF EXISTS "{constraint_name}"'))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_portfolio_positions_company_id ON portfolio_positions (company_id)"))


def main() -> None:
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
        _ensure_non_destructive_columns(conn)
    print("[watchTower] Tables created (or already exist).")

if __name__ == "__main__":
    main()
