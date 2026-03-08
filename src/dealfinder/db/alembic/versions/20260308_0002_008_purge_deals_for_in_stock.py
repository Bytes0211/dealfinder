"""Second purge — deals created between migration 007 and watchlist Lambda redeploy.

Revision ID: 008
Revises: 007
Create Date: 2026-03-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Delete deals created before in_stock Lambda deploy.

    Returns:
        None.
    """
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM notifications"))
    bind.execute(sa.text("DELETE FROM price_estimates"))
    bind.execute(sa.text("DELETE FROM deals"))


def downgrade() -> None:
    """No-op.

    Returns:
        None.
    """
    pass
