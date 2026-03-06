"""Drop category columns from deals and deal_sources tables.

Revision ID: 004
Revises: 003
Create Date: 2026-03-06

Changes:
- Drop ix_deals_category index from deals
- Drop deals.category column
- Drop ix_deal_sources_category index from deal_sources
- Drop deal_sources.category column
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop category columns and their indexes."""
    op.drop_index("ix_deals_category", table_name="deals")
    op.drop_column("deals", "category")

    op.drop_index("ix_deal_sources_category", table_name="deal_sources")
    op.drop_column("deal_sources", "category")


def downgrade() -> None:
    """Restore category columns and indexes."""
    op.add_column("deal_sources", sa.Column("category", sa.String(100), nullable=True))
    op.create_index("ix_deal_sources_category", "deal_sources", ["category"])

    op.add_column("deals", sa.Column("category", sa.String(100), nullable=True))
    op.create_index("ix_deals_category", "deals", ["category"])
