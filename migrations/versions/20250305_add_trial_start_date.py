"""add trial start date

Revision ID: add_trial_start_date
Revises: enhance_pharma_metrics
Create Date: 2025-03-05 01:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "add_trial_start_date"
down_revision = "enhance_pharma_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pharma_trials", sa.Column("start_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("pharma_trials", "start_date")
