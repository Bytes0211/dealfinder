"""Add phone_number, drop discount_threshold and preferred_categories from users.

Revision ID: 003
Revises: 002
Create Date: 2026-03-05

Changes:
- Drop users.discount_threshold column
- Drop users.preferred_categories column
- Add users.phone_number VARCHAR(20) nullable
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove category/threshold columns; add phone_number."""

    # Drop deprecated columns
    op.drop_column("users", "discount_threshold")
    op.drop_column("users", "preferred_categories")

    # Add phone number column for SNS SMS notifications
    op.add_column("users", sa.Column("phone_number", sa.String(20), nullable=True))


def downgrade() -> None:
    """Reverse: restore discount_threshold and preferred_categories, drop phone_number."""
    from sqlalchemy.dialects import postgresql

    op.drop_column("users", "phone_number")
    op.add_column(
        "users",
        sa.Column(
            "preferred_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "discount_threshold",
            sa.Numeric(precision=5, scale=2),
            server_default="20.00",
            nullable=False,
        ),
    )
