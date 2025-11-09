"""Add sales_and_marketing, general_and_administrative, other_income_expense.

Revision ID: 20241103_add_financial_gna_other
Revises: 20241015_add_pharma_tables
Create Date: 2025-11-03 01:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20241103_add_financial_gna_other"
down_revision = "add_pharma_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financials_annual",
        sa.Column("sales_and_marketing", sa.Numeric(20, 4), nullable=True),
    )
    op.add_column(
        "financials_annual",
        sa.Column("general_and_administrative", sa.Numeric(20, 4), nullable=True),
    )
    op.add_column(
        "financials_annual",
        sa.Column("other_income_expense", sa.Numeric(20, 4), nullable=True),
    )

    op.add_column(
        "financials_quarterly",
        sa.Column("sales_and_marketing", sa.Numeric(20, 4), nullable=True),
    )
    op.add_column(
        "financials_quarterly",
        sa.Column("general_and_administrative", sa.Numeric(20, 4), nullable=True),
    )
    op.add_column(
        "financials_quarterly",
        sa.Column("other_income_expense", sa.Numeric(20, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("financials_quarterly", "other_income_expense")
    op.drop_column("financials_quarterly", "general_and_administrative")
    op.drop_column("financials_quarterly", "sales_and_marketing")

    op.drop_column("financials_annual", "other_income_expense")
    op.drop_column("financials_annual", "general_and_administrative")
    op.drop_column("financials_annual", "sales_and_marketing")
