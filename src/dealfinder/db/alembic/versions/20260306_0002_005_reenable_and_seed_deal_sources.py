"""Re-enable and seed deal_sources from user saved feeds.

Revision ID: 005
Revises: 004
Create Date: 2026-03-06

Changes:
- Set deal_sources.is_active = true for all existing rows.
- Seed deal_sources rows for distinct saved_feeds URLs found in users'
  notification_preferences where a corresponding source URL does not yet exist.
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Re-enable existing sources and seed missing sources from saved feeds.

    Returns:
        None.
    """
    bind = op.get_bind()

    # 1) Re-enable all existing deal sources.
    bind.execute(sa.text("UPDATE deal_sources SET is_active = TRUE WHERE is_active IS DISTINCT FROM TRUE"))

    # 2) Gather existing URLs to avoid duplicate inserts.
    existing_urls_result = bind.execute(sa.text("SELECT url FROM deal_sources"))
    existing_urls: set[str] = {row[0] for row in existing_urls_result if row[0]}

    # 3) Read saved_feeds from active users and collect distinct URLs.
    prefs_result = bind.execute(
        sa.text(
            "SELECT notification_preferences "
            "FROM users "
            "WHERE is_active = TRUE "
            "AND notification_preferences IS NOT NULL"
        )
    )

    candidate_sources: dict[str, str] = {}
    for row in prefs_result:
        prefs = row[0] or {}
        if not isinstance(prefs, dict):
            continue
        saved_feeds = prefs.get("saved_feeds", []) or []
        if not isinstance(saved_feeds, list):
            continue

        for feed in saved_feeds:
            if not isinstance(feed, dict):
                continue
            url = str(feed.get("url", "")).strip()
            if not url or not (url.startswith("http://") or url.startswith("https://")):
                continue

            title = str(feed.get("title", "")).strip()
            query = str(feed.get("query", "")).strip()
            source_name = title or query or "Saved Feed Source"
            candidate_sources[url] = source_name[:255]

    # 4) Insert any missing URLs as active deal sources.
    insert_stmt = sa.text(
        "INSERT INTO deal_sources "
        "(id, name, url, is_active, check_interval_minutes, error_count, metadata, created_at, updated_at) "
        "VALUES (CAST(:id AS uuid), :name, :url, TRUE, 15, 0, CAST(:metadata AS jsonb), NOW(), NOW()) "
        "ON CONFLICT (url) DO NOTHING"
    )

    for url, name in candidate_sources.items():
        if url in existing_urls:
            continue
        bind.execute(
            insert_stmt,
            {
                "id": str(uuid.uuid4()),
                "name": name,
                "url": url,
                "metadata": "{}",
            },
        )


def downgrade() -> None:
    """No-op downgrade.

    This migration reconciles operational state from user-configured feed URLs.
    Reversing it would risk deleting legitimate production sources.

    Returns:
        None.
    """
    pass
