"""enhance pharma metrics

Revision ID: enhance_pharma_metrics
Revises: add_pharma_metadata
Create Date: 2025-03-05 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "enhance_pharma_metrics"
down_revision = "add_pharma_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pharma_trials",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "pharma_trials",
        sa.Column("status_last_verified", sa.Date(), nullable=True),
    )

    op.add_column(
        "pharma_drug_metadata",
        sa.Column("phase_override", sa.String(), nullable=True),
    )
    op.add_column(
        "pharma_drug_metadata",
        sa.Column("is_commercial", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "pharma_drug_metadata",
        sa.Column("peak_sales", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "pharma_drug_metadata",
        sa.Column("peak_sales_currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "pharma_drug_metadata",
        sa.Column("peak_sales_year", sa.Integer(), nullable=True),
    )
    op.add_column(
        "pharma_drug_metadata",
        sa.Column("probability_override", sa.Numeric(5, 2), nullable=True),
    )

    # Drop server defaults now that data is migrated
    op.alter_column(
        "pharma_trials",
        "is_active",
        existing_type=sa.Boolean(),
        server_default=None,
    )
    op.alter_column(
        "pharma_drug_metadata",
        "is_commercial",
        existing_type=sa.Boolean(),
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("pharma_drug_metadata", "probability_override")
    op.drop_column("pharma_drug_metadata", "peak_sales_year")
    op.drop_column("pharma_drug_metadata", "peak_sales_currency")
    op.drop_column("pharma_drug_metadata", "peak_sales")
    op.drop_column("pharma_drug_metadata", "is_commercial")
    op.drop_column("pharma_drug_metadata", "phase_override")

    op.drop_column("pharma_trials", "status_last_verified")
    op.drop_column("pharma_trials", "is_active")
