"""Purge existing deals to allow WatchlistAgent rediscovery with in_stock field.

Revision ID: 007
Revises: 006
Create Date: 2026-03-08

Changes:
- DELETE all rows from the deals table.
- The WatchlistAgent will rediscover deals on its next run, now with
  the in_stock field populated from Bedrock enrichment.

Background:
  The in_stock boolean was added to the Bedrock extraction prompt after
  existing deals were already persisted.  Deduplication by URL prevents
  re-processing, so a one-time purge is needed to refresh all deal data.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Delete all deals to allow fresh rediscovery with in_stock metadata.

    Returns:
        None.
    """
    bind = op.get_bind()
    # Delete dependent rows first to avoid FK constraint violations.
    bind.execute(sa.text("DELETE FROM notifications"))
    bind.execute(sa.text("DELETE FROM price_estimates"))
    bind.execute(sa.text("DELETE FROM deals"))


def downgrade() -> None:
    """No-op: deleted deal data cannot be restored.

    Returns:
        None.
    """
    pass
