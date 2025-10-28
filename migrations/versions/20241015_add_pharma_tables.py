"""add pharma tracking tables

Revision ID: add_pharma_tables
Revises: 1d19c780f037
Create Date: 2025-02-15 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_pharma_tables"
down_revision = "0c1eed1e8aed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pharma_companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("lead_sponsor", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("last_refreshed", sa.DateTime(), nullable=True),
        sa.Column("included_manually", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("company_id"),
        sa.UniqueConstraint("ticker"),
    )
    op.create_index("ix_pharma_companies_company_id", "pharma_companies", ["company_id"])
    op.create_index("ix_pharma_companies_ticker", "pharma_companies", ["ticker"])

    op.create_table(
        "pharma_drugs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pharma_company_id", sa.Integer(), sa.ForeignKey("pharma_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("indication", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("pharma_company_id", "name", name="uq_pharma_drug_company_name"),
    )
    op.create_index("ix_pharma_drugs_company_id", "pharma_drugs", ["pharma_company_id"])

    op.create_table(
        "pharma_trials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pharma_drug_id", sa.Integer(), sa.ForeignKey("pharma_drugs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("phase", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("condition", sa.String(), nullable=True),
        sa.Column("estimated_completion", sa.Date(), nullable=True),
        sa.Column("enrollment", sa.Integer(), nullable=True),
        sa.Column("success_probability", sa.Numeric(5, 2), nullable=True),
        sa.Column("sponsor", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("last_refreshed", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("nct_id"),
    )
    op.create_index("ix_pharma_trials_drug_id", "pharma_trials", ["pharma_drug_id"])
    op.create_index("ix_pharma_trial_phase_status", "pharma_trials", ["phase", "status"])


def downgrade() -> None:
    op.drop_index("ix_pharma_trial_phase_status", table_name="pharma_trials")
    op.drop_index("ix_pharma_trials_drug_id", table_name="pharma_trials")
    op.drop_table("pharma_trials")

    op.drop_index("ix_pharma_drugs_company_id", table_name="pharma_drugs")
    op.drop_table("pharma_drugs")

    op.drop_index("ix_pharma_companies_ticker", table_name="pharma_companies")
    op.drop_index("ix_pharma_companies_company_id", table_name="pharma_companies")
    op.drop_table("pharma_companies")
