"""add pharma drug sales table

Revision ID: add_pharma_sales
Revises: add_trial_start_date
Create Date: 2025-03-05 02:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "add_pharma_sales"
down_revision = "add_trial_start_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pharma_drug_metadata",
        sa.Column("segment", sa.String(), nullable=True),
    )

    op.create_table(
        "pharma_drug_sales",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "metadata_id",
            sa.Integer(),
            sa.ForeignKey("pharma_drug_metadata.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("period_type", sa.String(length=16), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_quarter", sa.SmallInteger(), nullable=True),
        sa.Column("revenue", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.UniqueConstraint(
            "metadata_id",
            "period_type",
            "period_year",
            "period_quarter",
            name="uq_pharma_drug_sales_period",
        ),
    )


def downgrade() -> None:
    op.drop_table("pharma_drug_sales")
    op.drop_column("pharma_drug_metadata", "segment")
