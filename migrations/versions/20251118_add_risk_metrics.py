"""add company risk metrics table

Revision ID: 20251118_add_risk_metrics
Revises: 20251118_add_favorite_companies
Create Date: 2025-11-18 19:45:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20251118_add_risk_metrics"
down_revision = "20251118_add_favorite_companies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_risk_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("beta", sa.Numeric(12, 6), nullable=True),
        sa.Column("alpha", sa.Numeric(12, 6), nullable=True),
        sa.Column("alpha_annual", sa.Numeric(12, 6), nullable=True),
        sa.Column("benchmark", sa.String(length=32), nullable=False, server_default="SPY"),
        sa.Column("risk_free_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("lookback_days", sa.Integer(), nullable=True),
        sa.Column("data_points", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("company_risk_metrics")
