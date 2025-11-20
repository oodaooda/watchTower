"""add favorite companies table

Revision ID: 20251118_add_favorite_companies
Revises: add_pharma_sales
Create Date: 2025-11-18 18:45:00.000000
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = "20251118_add_favorite_companies"
down_revision = "add_pharma_sales"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "favorite_companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("favorite_companies")
