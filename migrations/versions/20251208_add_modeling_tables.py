"""add modeling tables

Revision ID: 20251208_add_modeling_tables
Revises: 20251118_add_risk_metrics
Create Date: 2025-12-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251208_add_modeling_tables"
down_revision: Union[str, Sequence[str], None] = "20251118_extend_risk_windows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "modeling_assumptions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("scenario", sa.String(), nullable=False),
        sa.Column("revenue_cagr_start", sa.Numeric(8, 4)),
        sa.Column("revenue_cagr_floor", sa.Numeric(8, 4)),
        sa.Column("revenue_decay_quarters", sa.Integer()),
        sa.Column("gross_margin_target", sa.Numeric(8, 4)),
        sa.Column("gross_margin_glide_quarters", sa.Integer()),
        sa.Column("rnd_pct", sa.Numeric(8, 4)),
        sa.Column("sm_pct", sa.Numeric(8, 4)),
        sa.Column("ga_pct", sa.Numeric(8, 4)),
        sa.Column("tax_rate", sa.Numeric(8, 4)),
        sa.Column("interest_pct_revenue", sa.Numeric(8, 4)),
        sa.Column("dilution_pct_annual", sa.Numeric(8, 4)),
        sa.Column("seasonality_mode", sa.String(), server_default="auto"),
        sa.Column("driver_blend_start_weight", sa.Numeric(8, 4)),
        sa.Column("driver_blend_end_weight", sa.Numeric(8, 4)),
        sa.Column("driver_blend_ramp_quarters", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("company_id", "scenario", name="uq_modeling_assumptions_company_scenario"),
    )
    op.create_index("ix_modeling_assumptions_company", "modeling_assumptions", ["company_id"])

    op.create_table(
        "modeling_kpis",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.String(), nullable=False),
        sa.Column("mau", sa.Numeric(20, 4)),
        sa.Column("dau", sa.Numeric(20, 4)),
        sa.Column("paid_subs", sa.Numeric(20, 4)),
        sa.Column("paid_conversion_pct", sa.Numeric(8, 4)),
        sa.Column("arpu", sa.Numeric(20, 4)),
        sa.Column("churn_pct", sa.Numeric(8, 4)),
        sa.Column("source", sa.String(), server_default="manual"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("company_id", "fiscal_year", "fiscal_period", name="uq_modeling_kpis_company_year_period"),
    )
    op.create_index(
        "ix_modeling_kpis_company_year_period",
        "modeling_kpis",
        ["company_id", "fiscal_year", "fiscal_period"],
    )


def downgrade() -> None:
    op.drop_index("ix_modeling_kpis_company_year_period", table_name="modeling_kpis")
    op.drop_table("modeling_kpis")
    op.drop_index("ix_modeling_assumptions_company", table_name="modeling_assumptions")
    op.drop_table("modeling_assumptions")
