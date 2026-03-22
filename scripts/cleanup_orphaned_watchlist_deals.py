"""One-time cleanup script: remove orphaned watchlist deals from Top Deals.

Finds all watchlist:// DealSources whose query string is no longer referenced
by any active user's saved_feeds.  For each orphaned source, deletes all linked
deals and deactivates the source.

Usage:
    # Dry-run (default — shows what would be deleted, commits nothing)
    uv run python scripts/cleanup_orphaned_watchlist_deals.py

    # Live run
    uv run python scripts/cleanup_orphaned_watchlist_deals.py --execute

Environment:
    Reads DB connection from the same env vars / .env file as the app:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD  (or DB_SECRET_ARN on AWS)
"""

import argparse
import asyncio
import logging
import sys

from sqlalchemy import delete, select

from dealfinder.db.connection import get_async_session
from dealfinder.db.models import Deal, DealSource, User

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def find_orphaned_sources(session) -> list[DealSource]:
    """Return watchlist:// DealSources not referenced by any active user.

    Args:
        session: Active AsyncSession.

    Returns:
        List of DealSource rows that are orphaned.
    """
    # Collect all watchlist:// sources
    result = await session.execute(
        select(DealSource).where(DealSource.url.like("watchlist://%"))
    )
    watchlist_sources: list[DealSource] = list(result.scalars().all())

    if not watchlist_sources:
        return []

    # Collect all queries still watched by at least one active user
    users_result = await session.execute(
        select(User.notification_preferences).where(User.is_active == True)  # noqa: E712
    )
    active_queries: set[str] = set()
    for prefs in users_result.scalars().all():
        if not prefs:
            continue
        for feed in prefs.get("saved_feeds", []) or []:
            q = feed.get("query", "").lower().strip()
            if q:
                active_queries.add(q)

    orphaned = []
    for source in watchlist_sources:
        # Strip the "watchlist://" prefix to get the query
        query = source.url.removeprefix("watchlist://").lower().strip()
        if query not in active_queries:
            orphaned.append(source)

    return orphaned


async def cleanup(dry_run: bool) -> None:
    """Identify and optionally delete orphaned watchlist deals.

    Args:
        dry_run: If True, report findings without committing any deletions.
    """
    mode = "DRY RUN" if dry_run else "LIVE"
    logger.info("Starting orphaned watchlist deal cleanup  [%s]", mode)

    async with get_async_session() as session:
        orphaned_sources = await find_orphaned_sources(session)

        if not orphaned_sources:
            logger.info("No orphaned watchlist sources found. Nothing to do.")
            return

        logger.info("Found %d orphaned watchlist source(s):", len(orphaned_sources))
        for src in orphaned_sources:
            logger.info("  • %s  (id=%s, active=%s)", src.url, src.id, src.is_active)

        total_deals = 0
        for source in orphaned_sources:
            deals_result = await session.execute(
                select(Deal).where(Deal.source_id == source.id)
            )
            deals = deals_result.scalars().all()
            logger.info(
                "  %s → %d deal(s) would be deleted", source.url, len(deals)
            )
            total_deals += len(deals)

        if dry_run:
            logger.info(
                "DRY RUN complete. Would delete %d deal(s) across %d source(s). "
                "Re-run with --execute to apply.",
                total_deals,
                len(orphaned_sources),
            )
            # Prevent get_async_session from committing anything
            raise _Rollback()

        # --- Live deletion ---
        deleted_deals = 0
        for source in orphaned_sources:
            result = await session.execute(
                delete(Deal).where(Deal.source_id == source.id)
            )
            count = result.rowcount
            deleted_deals += count
            source.is_active = False
            logger.info(
                "Deleted %d deal(s) and deactivated source '%s'", count, source.url
            )

        logger.info(
            "Cleanup complete. Deleted %d deal(s) from %d source(s).",
            deleted_deals,
            len(orphaned_sources),
        )


class _Rollback(Exception):
    """Internal sentinel to abort the session without an error exit code."""


async def main() -> None:
    """Parse args and run cleanup.

    Raises:
        SystemExit: On argument errors.
    """
    parser = argparse.ArgumentParser(
        description="Remove orphaned watchlist deals from the database."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually delete records (default is dry-run only)",
    )
    args = parser.parse_args()

    try:
        await cleanup(dry_run=not args.execute)
    except _Rollback:
        pass  # Dry-run complete; session was rolled back cleanly
    except Exception:
        logger.exception("Cleanup failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
