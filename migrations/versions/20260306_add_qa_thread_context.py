"""add qa thread context table

Revision ID: 20260306_add_qa_thread_context
Revises: 20260305_add_earnings_transcripts_tables
Create Date: 2026-03-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260306_add_qa_thread_context"
down_revision: Union[str, Sequence[str], None] = "20260305_add_earnings_transcripts_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "qa_thread_context",
        sa.Column("thread_id", sa.String(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_qtc_company_id", "qa_thread_context", ["company_id"])
    op.create_index("ix_qtc_ticker", "qa_thread_context", ["ticker"])
    op.create_index("ix_qtc_updated_at", "qa_thread_context", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_qtc_updated_at", table_name="qa_thread_context")
    op.drop_index("ix_qtc_ticker", table_name="qa_thread_context")
    op.drop_index("ix_qtc_company_id", table_name="qa_thread_context")
    op.drop_table("qa_thread_context")
