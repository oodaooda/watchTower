"""add earnings transcript tables

Revision ID: 20260305_add_earnings_transcripts_tables
Revises: 20260220_add_llm_usage_tables
Create Date: 2026-03-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260305_add_earnings_transcripts_tables"
down_revision: Union[str, Sequence[str], None] = "20260220_add_llm_usage_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "earnings_call_transcripts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=False),
        sa.Column("call_date", sa.Date(), nullable=True),
        sa.Column("source_provider", sa.String(), nullable=False, server_default="alpha_vantage"),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source_doc_id", sa.String(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
        sa.Column("storage_mode", sa.String(), nullable=False, server_default="restricted"),
        sa.Column("ingested_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_quarter",
            "source_provider",
            name="uq_ect_company_period_provider",
        ),
    )
    op.create_index("ix_ect_company_id", "earnings_call_transcripts", ["company_id"])
    op.create_index("ix_ect_ticker", "earnings_call_transcripts", ["ticker"])
    op.create_index("ix_ect_fiscal_year", "earnings_call_transcripts", ["fiscal_year"])
    op.create_index("ix_ect_fiscal_quarter", "earnings_call_transcripts", ["fiscal_quarter"])
    op.create_index("ix_ect_company_period", "earnings_call_transcripts", ["company_id", "fiscal_year", "fiscal_quarter"])
    op.create_index("ix_ect_ticker_period", "earnings_call_transcripts", ["ticker", "fiscal_year", "fiscal_quarter"])

    op.create_table(
        "earnings_call_transcript_segments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "transcript_id",
            sa.Integer(),
            sa.ForeignKey("earnings_call_transcripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=True),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("transcript_id", "segment_index", name="uq_ect_segment_idx"),
    )
    op.create_index("ix_ect_segments_transcript", "earnings_call_transcript_segments", ["transcript_id"])


def downgrade() -> None:
    op.drop_index("ix_ect_segments_transcript", table_name="earnings_call_transcript_segments")
    op.drop_table("earnings_call_transcript_segments")

    op.drop_index("ix_ect_ticker_period", table_name="earnings_call_transcripts")
    op.drop_index("ix_ect_company_period", table_name="earnings_call_transcripts")
    op.drop_index("ix_ect_fiscal_quarter", table_name="earnings_call_transcripts")
    op.drop_index("ix_ect_fiscal_year", table_name="earnings_call_transcripts")
    op.drop_index("ix_ect_ticker", table_name="earnings_call_transcripts")
    op.drop_index("ix_ect_company_id", table_name="earnings_call_transcripts")
    op.drop_table("earnings_call_transcripts")
