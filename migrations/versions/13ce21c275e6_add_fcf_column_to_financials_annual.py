"""add fcf column to financials_annual

Revision ID: 13ce21c275e6
Revises: 1d19c780f037
Create Date: 2025-09-11 02:32:22.465696
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "13ce21c275e6"
down_revision: Union[str, Sequence[str], None] = "1d19c780f037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add fcf column."""
    op.add_column(
        "financials_annual",
        sa.Column("fcf", sa.Numeric(precision=20, scale=4), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema: drop fcf column."""
    op.drop_column("financials_annual", "fcf")
