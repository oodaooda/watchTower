"""add llm usage events and model prices

Revision ID: 20260220_add_llm_usage_tables
Revises: 20260102_add_settings_and_api_keys
Create Date: 2026-02-20 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260220_add_llm_usage_tables"
down_revision: Union[str, Sequence[str], None] = "20260102_add_settings_and_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="openai"),
        sa.Column("api", sa.String(), nullable=False, server_default="chat_completions"),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.String(), nullable=True),
        sa.Column("raw_usage_json", sa.String(), nullable=True),
    )
    op.create_index("ix_llm_usage_events_created_at", "llm_usage_events", ["created_at"])
    op.create_index("ix_llm_usage_events_endpoint", "llm_usage_events", ["endpoint"])
    op.create_index("ix_llm_usage_events_model", "llm_usage_events", ["model"])

    op.create_table(
        "llm_model_prices",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_per_million", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("output_per_million", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("cache_read_per_million", sa.Numeric(14, 6), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("provider", "model", name="uq_llm_model_prices_provider_model"),
    )
    op.create_index("ix_llm_model_prices_provider_model", "llm_model_prices", ["provider", "model"])


def downgrade() -> None:
    op.drop_index("ix_llm_model_prices_provider_model", table_name="llm_model_prices")
    op.drop_table("llm_model_prices")

    op.drop_index("ix_llm_usage_events_model", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_endpoint", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_created_at", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
