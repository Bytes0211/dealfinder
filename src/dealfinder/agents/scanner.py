"""ScannerAgent Lambda function for RSS feed processing.

Fetches all active deal sources from Aurora, parses each RSS feed with
feedparser, and persists newly discovered deals to the database.  Deals
already present (matched by source + external_id) are skipped to avoid
duplicates.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import feedparser
from sqlalchemy.ext.asyncio import AsyncSession

from dealfinder.agents.config import AgentConfig
from dealfinder.data.repository import DealRepository, DealSourceRepository
from dealfinder.db.connection import get_async_session
from dealfinder.db.models import Deal, DealSource, DealStatus

logger = logging.getLogger(__name__)


class ScannerAgent:
    """Scans RSS feeds and persists newly discovered deals to Aurora.

    Iterates over all active DealSource records, fetches each RSS feed,
    and creates Deal rows for entries that have not been seen before.
    Source health counters (last_checked_at, error_count) are updated
    after every fetch regardless of success.

    Example:
        agent = ScannerAgent()
        result = asyncio.run(agent.run())
        print(result["deals_discovered"])
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        """Initialise the scanner agent.

        Args:
            config: Agent configuration. Loaded from environment if not provided.
        """
        self.config = config or AgentConfig()

    async def scan_source(self, source: DealSource, session: AsyncSession) -> list[Deal]:
        """Fetch the RSS feed for one source and store any new deals.

        Args:
            source: Active DealSource to scan.
            session: Open AsyncSession shared with the caller.

        Returns:
            List of newly created Deal instances (may be empty).
        """
        deal_repo = DealRepository(session)
        source_repo = DealSourceRepository(session)

        logger.info(f"Scanning source: {source.name} ({source.url})")

        try:
            loop = asyncio.get_running_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, source.url)

            if feed.bozo and not feed.entries:
                logger.warning(f"Failed to parse feed for {source.name}: {feed.bozo_exception}")
                await source_repo.update_check_time(source.id, success=False)
                return []

            new_deals: list[Deal] = []
            for entry in feed.entries:
                external_id = (
                    entry.get("id")
                    or entry.get("link")
                    or hashlib.sha256(f"{source.id}:{entry.get('title', '')}".encode()).hexdigest()
                )

                existing = await deal_repo.get_by_external_id(source.id, external_id)
                if existing:
                    continue

                deal = Deal(
                    source_id=source.id,
                    external_id=external_id,
                    title=(entry.get("title") or "Untitled Deal")[:500],
                    description=entry.get("summary") or entry.get("description"),
                    url=entry.get("link") or "",
                    status=DealStatus.DISCOVERED,
                    raw_data={
                        "title": entry.get("title"),
                        "link": entry.get("link"),
                        "summary": entry.get("summary"),
                        "published": entry.get("published"),
                        "tags": [t.get("term") for t in entry.get("tags", [])],
                    },
                )
                created = await deal_repo.create(deal)
                new_deals.append(created)

            await source_repo.update_check_time(source.id, success=True)
            logger.info(f"Discovered {len(new_deals)} new deals from {source.name}")
            return new_deals

        except Exception as e:
            logger.error(f"Error scanning source {source.name}: {e}")
            await source_repo.update_check_time(source.id, success=False)
            return []

    async def run(self) -> dict:
        """Scan all active sources and return IDs of newly discovered deals.

        Opens a single database session for the full scan run and commits
        once all sources have been processed.

        Returns:
            Dictionary with keys:
                new_deal_ids: List of UUID strings for newly created deals.
                sources_scanned: Number of active sources processed.
                deals_discovered: Total count of new deals persisted.
                scanned_at: ISO-8601 timestamp of the scan start.
        """
        new_deal_ids: list[str] = []
        sources_scanned: int = 0

        async with get_async_session() as session:
            source_repo = DealSourceRepository(session)
            sources = await source_repo.find_active_sources()
            sources_scanned = len(sources)

            logger.info(f"Starting scan of {sources_scanned} active sources")

            for source in sources:
                new_deals = await self.scan_source(source, session)
                # Collect scalar IDs while the session is still open so that
                # Deal objects are not accessed in a detached / expired state.
                new_deal_ids.extend(str(d.id) for d in new_deals)

        return {
            "new_deal_ids": new_deal_ids,
            "sources_scanned": sources_scanned,
            "deals_discovered": len(new_deal_ids),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }


def handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point for the Scanner Agent.

    Args:
        event: Lambda invocation event. Unused; the scanner reads sources
            from the database rather than from the event payload.
        context: Lambda execution context (unused).

    Returns:
        Scan result dictionary with new_deal_ids and statistics.
    """
    return asyncio.run(ScannerAgent().run())
