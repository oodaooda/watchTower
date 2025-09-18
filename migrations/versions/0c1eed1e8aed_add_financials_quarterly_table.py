"""add financials_quarterly table

Revision ID: 0c1eed1e8aed
Revises: 13ce21c275e6
Create Date: 2025-09-11 10:05:14.370704

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c1eed1e8aed'
down_revision: Union[str, Sequence[str], None] = '13ce21c275e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create financials_quarterly table."""
    op.create_table(
        'financials_quarterly',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('fiscal_period', sa.String(), nullable=False),  # e.g. Q1, Q2, Q3, Q4
        sa.Column('report_date', sa.Date(), nullable=True),

        # Income Statement
        sa.Column('revenue', sa.Numeric(20, 4)),
        sa.Column('cost_of_revenue', sa.Numeric(20, 4)),
        sa.Column('gross_profit', sa.Numeric(20, 4)),
        sa.Column('research_and_development', sa.Numeric(20, 4)),
        sa.Column('selling_general_admin', sa.Numeric(20, 4)),
        sa.Column('operating_income', sa.Numeric(20, 4)),
        sa.Column('interest_expense', sa.Numeric(20, 4)),
        sa.Column('income_tax_expense', sa.Numeric(20, 4)),
        sa.Column('net_income', sa.Numeric(20, 4)),

        # Balance Sheet
        sa.Column('assets_total', sa.Numeric(20, 4)),
        sa.Column('liabilities_current', sa.Numeric(20, 4)),
        sa.Column('liabilities_longterm', sa.Numeric(20, 4)),
        sa.Column('equity_total', sa.Numeric(20, 4)),
        sa.Column('inventories', sa.Numeric(20, 4)),
        sa.Column('accounts_receivable', sa.Numeric(20, 4)),
        sa.Column('accounts_payable', sa.Numeric(20, 4)),
        sa.Column('cash_and_sti', sa.Numeric(20, 4)),
        sa.Column('total_debt', sa.Numeric(20, 4)),
        sa.Column('shares_outstanding', sa.Numeric(20, 4)),

        # Cash Flow
        sa.Column('cfo', sa.Numeric(20, 4)),
        sa.Column('capex', sa.Numeric(20, 4)),
        sa.Column('depreciation_amortization', sa.Numeric(20, 4)),
        sa.Column('share_based_comp', sa.Numeric(20, 4)),
        sa.Column('dividends_paid', sa.Numeric(20, 4)),
        sa.Column('share_repurchases', sa.Numeric(20, 4)),
        sa.Column('fcf', sa.Numeric(20, 4)),

        # Metadata
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('xbrl_confidence', sa.Numeric(6, 4)),

        sa.UniqueConstraint('company_id', 'fiscal_year', 'fiscal_period', name='uq_financials_q_company_year_period'),
    )

    # Indexes for performance
    op.create_index('ix_financials_q_company_year_period', 'financials_quarterly', ['company_id', 'fiscal_year', 'fiscal_period'])
    op.create_index('ix_financials_quarterly_company_id', 'financials_quarterly', ['company_id'])
    op.create_index('ix_financials_quarterly_fiscal_year', 'financials_quarterly', ['fiscal_year'])


def downgrade() -> None:
    """Downgrade schema: drop financials_quarterly table."""
    op.drop_index('ix_financials_quarterly_fiscal_year', table_name='financials_quarterly')
    op.drop_index('ix_financials_quarterly_company_id', table_name='financials_quarterly')
    op.drop_index('ix_financials_q_company_year_period', table_name='financials_quarterly')
    op.drop_table('financials_quarterly')
