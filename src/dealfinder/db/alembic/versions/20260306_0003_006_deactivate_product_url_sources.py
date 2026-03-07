"""Deactivate product-URL deal sources seeded by migration 005.

Revision ID: 006
Revises: 005
Create Date: 2026-03-06

Changes:
- Set deal_sources.is_active = FALSE for all rows whose URL begins with http://
  or https://.

Background:
  Migration 005 seeded deal_sources with product-page URLs extracted from users'
  saved Tavily search results (e.g. amazon.com/dp/...).  These are not valid RSS
  feeds and produce 0 entries when parsed by feedparser.  The WatchlistAgent
  creates correct watchlist:// sources on its first run and is the intended source
  of truth for user-query-driven deal discovery going forward.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deactivate all deal_sources with http/https URLs (product pages, not RSS feeds).

    Returns:
        None.
    """
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE deal_sources SET is_active = FALSE WHERE url LIKE 'http%'")
    )


def downgrade() -> None:
    """No-op: reversing would risk reactivating broken product-page sources.

    Returns:
        None.
    """
    pass
