"""WatchlistAgent Lambda function for scheduled Tavily + Bedrock deal discovery.

Reads all active users' saved watchlist feeds from Aurora, fires a Tavily search
for each unique query, enriches results via BedrockSearchExtractor (quality scoring
+ trend analysis), and persists new deals to the deals table.  Each query maps to
a DealSource with a watchlist:// URI so it is never confused with an RSS feed.

The existing watchlist/matches API endpoint picks up these deals via ILIKE keyword
matching on deal titles — no API changes required on that side.
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from dealfinder.agents.bedrock import BedrockSearchExtractor
from dealfinder.agents.config import AgentConfig
from dealfinder.data.repository import DealRepository, DealSourceRepository, UserRepository
from dealfinder.db.connection import get_async_session
from dealfinder.db.models import Deal, DealSource, DealStatus

logger = logging.getLogger(__name__)

_TAVILY_API_URL = "https://api.tavily.com/search"
_LAMBDA_LOOP: asyncio.AbstractEventLoop | None = None


def _normalize_query(query: str) -> str:
    """Return a normalized query string for use as a DealSource URL slug.

    Args:
        query: Raw feed query string.

    Returns:
        Lowercased, stripped query string.
    """
    return query.lower().strip()


def _watchlist_url(query: str) -> str:
    """Return the canonical watchlist:// URI for a query.

    Args:
        query: Raw or normalized feed query string.

    Returns:
        URI string, e.g. ``watchlist://sony headphones``.
    """
    return f"watchlist://{_normalize_query(query)}"


def _parse_price(value: str | None) -> Decimal | None:
    """Parse a price string like '$279.99' into a Decimal.

    Strips currency symbols, commas, and whitespace. Returns None if the
    value is missing, empty, or cannot be parsed as a positive number.

    Args:
        value: Raw price string from Bedrock enrichment, e.g. ``"$1,299.99"``.

    Returns:
        Decimal price or None if unparsable.
    """
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value.strip())
    if not cleaned:
        return None
    try:
        d = Decimal(cleaned).quantize(Decimal("0.01"))
        return d if d > 0 else None
    except (InvalidOperation, ArithmeticError):
        return None


class WatchlistAgent:
    """Scheduled Lambda agent that discovers deals from user watchlist queries.

    For each unique query across all active users' saved feeds, the agent:

    1. Finds or creates a ``DealSource`` with ``url = watchlist://<query>``.
    2. Calls Tavily to search the web for the query.
    3. Enriches results with ``BedrockSearchExtractor`` (quality score + trend analysis).
    4. Persists new deals (deduped by source + sha256(url)) to Aurora.

    The ``watchlist/matches`` API endpoint picks up these deals via the existing
    ILIKE keyword matching on deal titles — no API changes required.

    Example:
        agent = WatchlistAgent()
        result = asyncio.run(agent.run())
        print(result["deals_discovered"])
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        """Initialise the watchlist agent.

        Args:
            config: Agent configuration. Loaded from environment if not provided.
        """
        self.config = config or AgentConfig()

    async def _get_or_create_source(self, query: str, session: AsyncSession) -> DealSource:
        """Find an existing DealSource for this query or create a new one.

        Args:
            query: Watchlist query string.
            session: Open AsyncSession.

        Returns:
            Existing or newly created DealSource.
        """
        repo = DealSourceRepository(session)
        url = _watchlist_url(query)
        source = await repo.get_by_url(url)
        if source:
            return source

        new_source = DealSource(
            name=query[:255],
            url=url,
            is_active=True,
            check_interval_minutes=30,
        )
        try:
            async with session.begin_nested():
                source = await repo.create(new_source)
        except Exception:
            # Race: a concurrent invocation created the row first — re-fetch it.
            source = await repo.get_by_url(url)
            if not source:
                raise
        return source

    async def _call_tavily(self, query: str) -> list[dict]:
        """Fetch Tavily search results for a query.

        Args:
            query: Search query string.

        Returns:
            List of raw Tavily result dicts. Empty list on any error.
        """
        api_key = self.config.tavily_api_key
        if not api_key:
            logger.warning("Tavily API key not configured — skipping query '%s'", query)
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    _TAVILY_API_URL,
                    json={
                        "api_key": api_key,
                        "query": query,
                        "search_depth": "basic",
                        "max_results": 10,
                        "include_answer": False,
                        "include_raw_content": False,
                        "exclude_domains": [
                            "youtube.com",
                            "reddit.com",
                            "twitter.com",
                            "facebook.com",
                        ],
                    },
                )
                response.raise_for_status()
                return response.json().get("results", [])
        except httpx.TimeoutException:
            logger.warning("Tavily timeout for query '%s'", query)
            return []
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Tavily HTTP %d for query '%s'", exc.response.status_code, query
            )
            return []
        except Exception as exc:
            logger.error("Tavily unexpected error for query '%s': %s", query, exc)
            return []

    async def search_query(self, query: str, session: AsyncSession) -> list[Deal]:
        """Search Tavily for a query, enrich with Bedrock, and persist new deals.

        Args:
            query: Watchlist search query string.
            session: Open AsyncSession.

        Returns:
            List of newly created Deal instances (may be empty).
        """
        source_repo = DealSourceRepository(session)
        deal_repo = DealRepository(session)

        source = await self._get_or_create_source(query, session)

        # Append "buy price" to bias Tavily toward product listing pages
        # rather than reviews/articles, increasing price extraction rate.
        search_query = f"{query} buy price"
        raw_results = await self._call_tavily(search_query)
        if not raw_results:
            await source_repo.update_check_time(source.id, success=False)
            return []

        # Bedrock enrichment with trend analysis — blocking boto3 call in executor.
        extractor = BedrockSearchExtractor(self.config)
        loop = asyncio.get_running_loop()
        try:
            enriched = await loop.run_in_executor(
                None, lambda: extractor.extract(raw_results, include_trends=True)
            )
        except Exception as exc:
            logger.warning("Bedrock enrichment failed for '%s': %s", query, exc)
            enriched = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "current_price": None,
                    "quality_score": None,
                    "quality_reason": None,
                }
                for r in raw_results
            ]

        new_deals: list[Deal] = []
        for result in enriched:
            url = result.get("url", "")
            if not url:
                continue

            external_id = hashlib.sha256(url.encode()).hexdigest()
            existing = await deal_repo.get_by_external_id(source.id, external_id)
            if existing:
                continue

            quality_score = result.get("quality_score")
            is_high_value = bool(quality_score is not None and float(quality_score) >= 7.0)

            sale_price = _parse_price(result.get("current_price"))
            if sale_price is None:
                continue

            deal = Deal(
                source_id=source.id,
                external_id=external_id,
                title=(result.get("title") or query)[:500],
                url=url,
                sale_price=sale_price,
                status=DealStatus.EVALUATED,
                is_high_value=is_high_value,
                raw_data=result,
            )
            try:
                async with session.begin_nested():
                    created = await deal_repo.create(deal)
                new_deals.append(created)
            except Exception as exc:
                logger.warning(
                    "Skipping deal %s for query '%s': %s", external_id[:12], query, exc
                )

        try:
            await source_repo.update_check_time(source.id, success=True)
        except Exception as exc:
            logger.warning("Failed to update check time for source '%s': %s", query, exc)

        logger.info("Query '%s': %d new deals discovered", query, len(new_deals))
        return new_deals

    async def run(self) -> dict:
        """Run the watchlist agent across all users' saved feed queries.

        Collects unique queries from all active users' ``saved_feeds``, runs a
        Tavily + Bedrock search per query, and persists new deals to Aurora.

        Returns:
            Dictionary with keys:
                queries_searched: Number of unique queries processed.
                deals_discovered: Total count of new deals persisted.
                scanned_at: ISO-8601 timestamp of the run start.
        """
        new_deal_ids: list[str] = []
        queries_searched: int = 0

        async with get_async_session() as session:
            user_repo = UserRepository(session)
            users = await user_repo.find_active_users()

            # Collect unique queries preserving first-seen order.
            seen_normalized: set[str] = set()
            queries: list[str] = []
            for user in users:
                prefs = user.notification_preferences or {}
                for feed in prefs.get("saved_feeds", []) or []:
                    if not isinstance(feed, dict):
                        continue
                    q = str(feed.get("query", "")).strip()
                    norm = _normalize_query(q)
                    if q and norm not in seen_normalized:
                        seen_normalized.add(norm)
                        queries.append(q)

            queries_searched = len(queries)
            logger.info("WatchlistAgent: processing %d unique queries", queries_searched)

            for query in queries:
                new_deals = await self.search_query(query, session)
                new_deal_ids.extend(str(d.id) for d in new_deals)

        return {
            "queries_searched": queries_searched,
            "deals_discovered": len(new_deal_ids),
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }


def handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point for the WatchlistAgent.

    Args:
        event: Lambda invocation event (unused; queries are read from the DB).
        context: Lambda execution context (unused).

    Returns:
        Result dictionary with queries_searched, deals_discovered, scanned_at.
    """
    global _LAMBDA_LOOP

    if _LAMBDA_LOOP is None or _LAMBDA_LOOP.is_closed():
        _LAMBDA_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LAMBDA_LOOP)

    return _LAMBDA_LOOP.run_until_complete(WatchlistAgent().run())
