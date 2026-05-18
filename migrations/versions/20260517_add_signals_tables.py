"""add signals tables

Revision ID: 20260517_add_signals_tables
Revises: 20260306_add_qa_thread_context
Create Date: 2026-05-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_add_signals_tables"
down_revision: Union[str, Sequence[str], None] = "20260306_add_qa_thread_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("module_id", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False, server_default=""),
        sa.Column("metric", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="grey"),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("module_id", "ts", "metric", "entity", name="uq_signals_module_ts_metric_entity"),
    )
    op.create_index("ix_signals_ts", "signals", ["ts"])
    op.create_index("ix_signals_module_id", "signals", ["module_id"])
    op.create_index("ix_signals_module_ts", "signals", ["module_id", "ts"])
    op.create_index("ix_signals_metric_entity_ts", "signals", ["metric", "entity", "ts"])

    op.create_table(
        "signal_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("module_id", sa.String(), nullable=False),
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signals.id", ondelete="CASCADE"), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index("ix_signal_events_ts", "signal_events", ["ts"])
    op.create_index("ix_signal_events_module_id", "signal_events", ["module_id"])

    op.create_table(
        "signal_ingest_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("module_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("records_written", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_signal_ingest_runs_module_id", "signal_ingest_runs", ["module_id"])

    op.create_table(
        "signal_module_state",
        sa.Column("module_id", sa.String(), primary_key=True, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "signal_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("module_id", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_reason", sa.String(), nullable=True),
        sa.Column("state_snapshot", sa.JSON(), nullable=True),
    )
    op.create_index("ix_signal_alerts_ts", "signal_alerts", ["ts"])
    op.create_index("ix_signal_alerts_module_id", "signal_alerts", ["module_id"])

    op.create_table(
        "signal_layouts",
        sa.Column("key_hash", sa.String(), primary_key=True, nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "signal_goal_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("goal_name", sa.String(), nullable=False, server_default="portfolio_1m"),
        sa.Column("current_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("target_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("distance_to_goal", sa.Numeric(20, 4), nullable=False),
        sa.Column("velocity_30d", sa.Numeric(20, 4), nullable=True),
        sa.Column("velocity_90d", sa.Numeric(20, 4), nullable=True),
        sa.Column("required_monthly_gain", sa.Numeric(20, 4), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_signal_goal_snapshots_goal_ts", "signal_goal_snapshots", ["goal_name", "ts"])


def downgrade() -> None:
    op.drop_index("ix_signal_goal_snapshots_goal_ts", table_name="signal_goal_snapshots")
    op.drop_table("signal_goal_snapshots")
    op.drop_table("signal_layouts")
    op.drop_index("ix_signal_alerts_module_id", table_name="signal_alerts")
    op.drop_index("ix_signal_alerts_ts", table_name="signal_alerts")
    op.drop_table("signal_alerts")
    op.drop_table("signal_module_state")
    op.drop_index("ix_signal_ingest_runs_module_id", table_name="signal_ingest_runs")
    op.drop_table("signal_ingest_runs")
    op.drop_index("ix_signal_events_module_id", table_name="signal_events")
    op.drop_index("ix_signal_events_ts", table_name="signal_events")
    op.drop_table("signal_events")
    op.drop_index("ix_signals_metric_entity_ts", table_name="signals")
    op.drop_index("ix_signals_module_ts", table_name="signals")
    op.drop_index("ix_signals_module_id", table_name="signals")
    op.drop_index("ix_signals_ts", table_name="signals")
    op.drop_table("signals")
