"""Lambda handler: one-time cleanup of orphaned watchlist deals.

Invoked by scripts/run-cleanup-lambda.sh which temporarily swaps the API
Lambda handler to this module, runs it synchronously, then restores the
original handler.

A watchlist:// DealSource is considered orphaned when no active user's
saved_feeds references its query string.  All deals linked to an orphaned
source are deleted and the source is deactivated.

Expected event payload::

    {"dry_run": true}   # preview only (default)
    {"dry_run": false}  # actually delete
"""

import asyncio
import json
import logging
import os

from sqlalchemy import delete, select

from dealfinder.db.connection import close_engine, get_async_session
from dealfinder.db.models import Deal, DealSource, User

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def _find_orphaned_sources(session) -> list[DealSource]:
    """Return watchlist:// DealSources not referenced by any active user.

    Args:
        session: Active AsyncSession.

    Returns:
        List of orphaned DealSource rows.
    """
    result = await session.execute(
        select(DealSource).where(DealSource.url.like("watchlist://%"))
    )
    watchlist_sources: list[DealSource] = list(result.scalars().all())

    if not watchlist_sources:
        return []

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

    return [
        src for src in watchlist_sources
        if src.url.removeprefix("watchlist://").lower().strip() not in active_queries
    ]


async def _run_cleanup(dry_run: bool) -> dict:
    """Identify and optionally delete orphaned watchlist deals.

    Args:
        dry_run: If True, report findings without committing deletions.

    Returns:
        Result dict with status, orphaned_sources, deals_deleted, dry_run flag.
    """
    async with get_async_session() as session:
        orphaned = await _find_orphaned_sources(session)

        if not orphaned:
            logger.info("No orphaned watchlist sources found.")
            return {
                "status": "ok",
                "dry_run": dry_run,
                "orphaned_sources": 0,
                "deals_deleted": 0,
                "message": "No orphaned watchlist sources found.",
            }

        source_details = []
        total_deals = 0
        for src in orphaned:
            count_result = await session.execute(
                select(Deal).where(Deal.source_id == src.id)
            )
            deals = count_result.scalars().all()
            deal_count = len(deals)
            total_deals += deal_count
            source_details.append({
                "url": src.url,
                "source_id": str(src.id),
                "deal_count": deal_count,
            })
            logger.info("Orphaned: %s (%d deal(s))", src.url, deal_count)

        if dry_run:
            logger.info(
                "DRY RUN: would delete %d deal(s) from %d source(s)",
                total_deals, len(orphaned),
            )
            raise _AbortSession(
                result={
                    "status": "dry_run",
                    "dry_run": True,
                    "orphaned_sources": len(orphaned),
                    "deals_deleted": total_deals,
                    "sources": source_details,
                    "message": (
                        f"Dry run: would delete {total_deals} deal(s) "
                        f"from {len(orphaned)} source(s)."
                    ),
                }
            )

        # Live deletion
        deleted = 0
        for src in orphaned:
            result = await session.execute(
                delete(Deal).where(Deal.source_id == src.id)
            )
            deleted += result.rowcount
            src.is_active = False
            logger.info("Deleted %d deal(s), deactivated %s", result.rowcount, src.url)

        msg = f"Deleted {deleted} deal(s) from {len(orphaned)} orphaned source(s)."
        logger.info(msg)
        return {
            "status": "ok",
            "dry_run": False,
            "orphaned_sources": len(orphaned),
            "deals_deleted": deleted,
            "sources": source_details,
            "message": msg,
        }


class _AbortSession(Exception):
    """Carries the dry-run result out of the session context manager."""

    def __init__(self, result: dict) -> None:
        """Initialise with the result payload.

        Args:
            result: Dict to return to the caller.
        """
        self.result = result


def handler(event: dict, context) -> dict:
    """AWS Lambda entry point for the orphaned-deal cleanup task.

    Args:
        event: Lambda event payload. Recognised keys:
            dry_run (bool): If True (default), report only — do not delete.
        context: Lambda context (unused).

    Returns:
        Result dict with status, message, and counts.
    """
    dry_run: bool = event.get("dry_run", True)
    logger.info("cleanup_handler invoked  dry_run=%s", dry_run)

    async def _main() -> dict:
        try:
            result = await _run_cleanup(dry_run=dry_run)
        except _AbortSession as exc:
            result = exc.result
        finally:
            await close_engine()
        return result

    try:
        return asyncio.run(_main())
    except Exception as exc:
        logger.exception("Cleanup handler failed")
        return {"status": "error", "message": str(exc)}
