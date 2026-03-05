"""Replace Pushover with SNS in notification channel enum.

Revision ID: 002
Revises: 001
Create Date: 2026-03-05

Changes:
- Recreate notificationchannel enum: replace 'pushover' with 'sns'
- Drop pushover_user_key column from users table
- Make notifications.user_id nullable (SNS broadcast rows have no single user)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate Pushover → SNS."""

    # ── 1. Recreate notificationchannel enum ──────────────────────────────────
    # PostgreSQL does not support removing values from an enum directly.
    # Strategy: rename old type, create new type, migrate column, drop old type.

    # Convert existing 'pushover' rows to 'sns' before swapping the type
    op.execute("UPDATE notifications SET channel = 'sns' WHERE channel = 'pushover'")

    # Rename old enum so it can be dropped after the column is migrated
    op.execute("ALTER TYPE notificationchannel RENAME TO notificationchannel_old")

    # Create the new enum without 'pushover'
    op.execute("CREATE TYPE notificationchannel AS ENUM ('email', 'sns', 'sms', 'websocket')")

    # Migrate the column to use the new enum type
    op.execute(
        "ALTER TABLE notifications "
        "ALTER COLUMN channel TYPE notificationchannel "
        "USING channel::text::notificationchannel"
    )

    # Drop the old enum type
    op.execute("DROP TYPE notificationchannel_old")

    # ── 2. Drop pushover_user_key from users ──────────────────────────────────
    op.drop_column("users", "pushover_user_key")

    # ── 3. Make notifications.user_id nullable (for SNS broadcast rows) ───────
    op.alter_column("notifications", "user_id", nullable=True)


def downgrade() -> None:
    """Reverse: restore Pushover enum value and pushover_user_key column."""

    # Restore user_id to NOT NULL (requires no NULL rows exist)
    op.alter_column("notifications", "user_id", nullable=False)

    # Restore pushover_user_key column
    op.add_column("users", sa.Column("pushover_user_key", sa.String(255), nullable=True))

    # Recreate enum with 'pushover' and without 'sns'
    op.execute("UPDATE notifications SET channel = 'pushover' WHERE channel = 'sns'")
    op.execute("ALTER TYPE notificationchannel RENAME TO notificationchannel_old")
    op.execute(
        "CREATE TYPE notificationchannel AS ENUM ('email', 'pushover', 'sms', 'websocket')"
    )
    op.execute(
        "ALTER TABLE notifications "
        "ALTER COLUMN channel TYPE notificationchannel "
        "USING channel::text::notificationchannel"
    )
    op.execute("DROP TYPE notificationchannel_old")
