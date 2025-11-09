"""add pharma drug metadata

Revision ID: add_pharma_metadata
Revises: 20241103_add_financial_gna_other
Create Date: 2025-02-15 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "add_pharma_metadata"
down_revision = "20241103_add_financial_gna_other"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pharma_trials", sa.Column("has_results", sa.Boolean(), nullable=True))
    op.add_column("pharma_trials", sa.Column("why_stopped", sa.String(), nullable=True))

    op.create_table(
        "pharma_drug_metadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("drug_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("ticker", "drug_name", name="uq_pharma_drug_metadata_ticker_name"),
    )
    op.create_index("ix_pharma_drug_metadata_ticker", "pharma_drug_metadata", ["ticker"])


def downgrade() -> None:
    op.drop_column("pharma_trials", "why_stopped")
    op.drop_column("pharma_trials", "has_results")

    op.drop_index("ix_pharma_drug_metadata_ticker", table_name="pharma_drug_metadata")
    op.drop_table("pharma_drug_metadata")
