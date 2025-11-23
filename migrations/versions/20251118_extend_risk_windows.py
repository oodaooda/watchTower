"""add shorter alpha windows

Revision ID: 20251118_extend_risk_windows
Revises: 20251118_add_risk_metrics
Create Date: 2025-11-21 14:05:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20251118_extend_risk_windows"
down_revision = "20251118_add_risk_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_risk_metrics",
        sa.Column("alpha_annual_1y", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "company_risk_metrics",
        sa.Column("alpha_annual_6m", sa.Numeric(12, 6), nullable=True),
    )
    op.add_column(
        "company_risk_metrics",
        sa.Column("alpha_annual_3m", sa.Numeric(12, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_risk_metrics", "alpha_annual_3m")
    op.drop_column("company_risk_metrics", "alpha_annual_6m")
    op.drop_column("company_risk_metrics", "alpha_annual_1y")
