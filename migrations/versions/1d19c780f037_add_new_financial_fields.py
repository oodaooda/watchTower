"""add new financial fields

Revision ID: 1d19c780f037
Revises: 
Create Date: 2025-09-11 00:09:01.625958
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d19c780f037'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_not_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = :table AND column_name = :column
    """), {"table": table, "column": column}).fetchone()
    return result is None

def upgrade() -> None:
    """Upgrade schema by adding detailed financial fields."""

    # Income Statement
    if column_not_exists("financials_annual", "cost_of_revenue"):
        op.add_column("financials_annual", sa.Column("cost_of_revenue", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "research_and_development"):
        op.add_column("financials_annual", sa.Column("research_and_development", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "selling_general_admin"):
        op.add_column("financials_annual", sa.Column("selling_general_admin", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "interest_expense"):
        op.add_column("financials_annual", sa.Column("interest_expense", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "income_tax_expense"):
        op.add_column("financials_annual", sa.Column("income_tax_expense", sa.Numeric(20, 4)))

    # Balance Sheet
    if column_not_exists("financials_annual", "liabilities_current"):
        op.add_column("financials_annual", sa.Column("liabilities_current", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "liabilities_longterm"):
        op.add_column("financials_annual", sa.Column("liabilities_longterm", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "inventories"):
        op.add_column("financials_annual", sa.Column("inventories", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "accounts_receivable"):
        op.add_column("financials_annual", sa.Column("accounts_receivable", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "accounts_payable"):
        op.add_column("financials_annual", sa.Column("accounts_payable", sa.Numeric(20, 4)))

    # Cash Flow
    if column_not_exists("financials_annual", "depreciation_amortization"):
        op.add_column("financials_annual", sa.Column("depreciation_amortization", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "share_based_comp"):
        op.add_column("financials_annual", sa.Column("share_based_comp", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "dividends_paid"):
        op.add_column("financials_annual", sa.Column("dividends_paid", sa.Numeric(20, 4)))
    if column_not_exists("financials_annual", "share_repurchases"):
        op.add_column("financials_annual", sa.Column("share_repurchases", sa.Numeric(20, 4)))