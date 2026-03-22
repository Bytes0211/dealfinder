"""Unit tests for WatchlistAgent.

Uses an in-memory SQLite database and mocked Tavily/Bedrock calls to exercise
deal persistence logic without network or real AWS dependencies.
"""

import hashlib
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from dealfinder.agents.bedrock import PriceEstimationResult
from dealfinder.agents.config import AgentConfig
from dealfinder.agents.watchlist import WatchlistAgent, _normalize_query, _watchlist_url
from dealfinder.data.repository import UserRepository
from dealfinder.db.models import Base, DealSource, DealStatus, User


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def engine():
    """In-memory SQLite engine with PostgreSQL type overrides."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(eng.sync_engine, "connect")
    def _pragma(dbapi_conn, _record):
        """Enable foreign keys for SQLite."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    """Open database session bound to the in-memory engine."""
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest.fixture
def config() -> AgentConfig:
    """AgentConfig with a fake Tavily key so the agent does not short-circuit."""
    return AgentConfig(
        tavily_api_key="test-tavily-key",
        bedrock_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        notification_queue_url="",
    )


@pytest.fixture
async def user_with_feeds(session) -> User:
    """Active user with two saved watchlist feeds."""
    user = User(
        email="alice@example.com",
        username="alice",
        hashed_password="hashed",
        is_active=True,
        notification_preferences={
            "saved_feeds": [
                {
                    "id": "feed-1",
                    "query": "Sony headphones",
                    "title": "Sony WH-1000XM5",
                    "url": "https://example.com/sony",
                    "saved_at": "2026-03-06T00:00:00Z",
                },
                {
                    "id": "feed-2",
                    "query": "mechanical keyboard",
                    "title": "Mechanical Keyboard",
                    "url": "https://example.com/kb",
                    "saved_at": "2026-03-06T00:00:00Z",
                },
            ]
        },
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _make_tavily_results(urls: list[str]) -> list[dict]:
    """Build minimal Tavily-style results for the given URLs."""
    return [
        {
            "title": f"Product at {url}",
            "url": url,
            "content": "Great deal on a product.",
        }
        for url in urls
    ]


def _make_bedrock_results(urls: list[str], include_trends: bool = False) -> list[dict]:
    """Build minimal Bedrock-enriched results matching the given URLs."""
    results = []
    for url in urls:
        r: dict = {
            "title": f"Product at {url}",
            "url": url,
            "current_price": "$299.99",
            "quality_score": 8.0,
            "quality_reason": "Great value",
        }
        if include_trends:
            r.update({
                "trend": "upward",
                "trend_confidence": 0.85,
                "price_trend": "stable",
                "discount_frequency": "low",
                "stockouts_last_30_days": 2,
                "review_velocity": "high",
                "competitor_activity": "stable",
                "trend_summary": "Strong demand with low discount frequency.",
            })
        results.append(r)
    return results


def _make_price_estimation(estimated_price: str = "349.99", confidence: str = "0.85") -> PriceEstimationResult:
    """Build a PriceEstimationResult for mocking BedrockPriceEstimator."""
    return PriceEstimationResult(
        estimated_price=Decimal(estimated_price),
        confidence=Decimal(confidence),
        range_low=None,
        range_high=None,
        model_id="test-model",
        inference_time_ms=100,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_normalize_query_lowercases_and_strips(self) -> None:
        """Normalize should lowercase and strip whitespace."""
        assert _normalize_query("  Sony Headphones  ") == "sony headphones"

    def test_watchlist_url_format(self) -> None:
        """watchlist:// URI should use the normalized query as the slug."""
        assert _watchlist_url("Sony Headphones") == "watchlist://sony headphones"


class TestWatchlistAgentNoUsers:
    """WatchlistAgent with no users in the database."""

    async def test_no_users_returns_empty_result(self, config: AgentConfig) -> None:
        """When there are no users, the agent should return 0 queries searched."""
        agent = WatchlistAgent(config=config)

        with patch(
            "dealfinder.agents.watchlist.get_async_session"
        ) as mock_ctx:
            session_mock = AsyncMock()
            session_mock.__aenter__ = AsyncMock(return_value=session_mock)
            session_mock.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = session_mock

            with patch.object(
                UserRepository, "find_active_users", new_callable=AsyncMock, return_value=[]
            ):
                result = await agent.run()

        assert result["queries_searched"] == 0
        assert result["deals_discovered"] == 0
        assert "scanned_at" in result


class TestWatchlistAgentNoFeeds:
    """WatchlistAgent when users exist but have no saved feeds."""

    async def test_no_saved_feeds_returns_empty_result(
        self, config: AgentConfig
    ) -> None:
        """User with no saved_feeds should produce 0 queries searched."""
        agent = WatchlistAgent(config=config)

        user = MagicMock()
        user.notification_preferences = {}

        with patch(
            "dealfinder.agents.watchlist.get_async_session"
        ) as mock_ctx:
            session_mock = AsyncMock()
            session_mock.__aenter__ = AsyncMock(return_value=session_mock)
            session_mock.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = session_mock

            with patch.object(
                UserRepository,
                "find_active_users",
                new_callable=AsyncMock,
                return_value=[user],
            ):
                result = await agent.run()

        assert result["queries_searched"] == 0
        assert result["deals_discovered"] == 0


class TestWatchlistAgentSearchQuery:
    """Tests for WatchlistAgent.search_query (core deal persistence logic)."""

    async def test_new_deals_persisted_with_trend_data(
        self, session: AsyncSession, config: AgentConfig
    ) -> None:
        """New Tavily results should be persisted with trend fields stored in raw_data."""
        agent = WatchlistAgent(config=config)
        agent._estimator = MagicMock()
        agent._estimator.estimate_price.return_value = _make_price_estimation()
        urls = ["https://amazon.com/dp/B001", "https://bestbuy.com/p/12345"]
        tavily_results = _make_tavily_results(urls)
        bedrock_results = _make_bedrock_results(urls, include_trends=True)

        with patch.object(agent, "_call_tavily", new_callable=AsyncMock, return_value=tavily_results), \
             patch("dealfinder.agents.watchlist.BedrockSearchExtractor") as MockExtractor:
            mock_extractor = MagicMock()
            mock_extractor.extract.return_value = bedrock_results
            MockExtractor.return_value = mock_extractor

            new_deals = await agent.search_query("Sony headphones", session)

        assert len(new_deals) == 2
        for deal in new_deals:
            assert deal.status == DealStatus.EVALUATED
            assert deal.is_high_value is True
            assert deal.raw_data is not None
            assert deal.raw_data["trend"] == "upward"
            assert deal.raw_data["trend_confidence"] == 0.85
            assert deal.raw_data["review_velocity"] == "high"
            assert deal.raw_data["trend_summary"] == "Strong demand with low discount frequency."
            assert "price_sanity_check" in deal.raw_data

    async def test_deduplication_skips_existing_deals(
        self, session: AsyncSession, config: AgentConfig
    ) -> None:
        """A second search_query call with the same URL should not create a duplicate deal."""
        agent = WatchlistAgent(config=config)
        agent._estimator = MagicMock()
        agent._estimator.estimate_price.return_value = _make_price_estimation()
        urls = ["https://amazon.com/dp/DEDUP001"]
        tavily_results = _make_tavily_results(urls)
        bedrock_results = _make_bedrock_results(urls)

        with patch.object(agent, "_call_tavily", new_callable=AsyncMock, return_value=tavily_results), \
             patch("dealfinder.agents.watchlist.BedrockSearchExtractor") as MockExtractor:
            mock_extractor = MagicMock()
            mock_extractor.extract.return_value = bedrock_results
            MockExtractor.return_value = mock_extractor

            first = await agent.search_query("test query", session)
            await session.commit()

            second = await agent.search_query("test query", session)

        assert len(first) == 1
        assert len(second) == 0

    async def test_tavily_failure_marks_source_error(
        self, session: AsyncSession, config: AgentConfig
    ) -> None:
        """When Tavily returns empty results, source should be marked as failed."""
        agent = WatchlistAgent(config=config)

        with patch.object(agent, "_call_tavily", new_callable=AsyncMock, return_value=[]):
            new_deals = await agent.search_query("failing query", session)

        assert new_deals == []

        from dealfinder.data.repository import DealSourceRepository
        source_repo = DealSourceRepository(session)
        source = await source_repo.get_by_url("watchlist://failing query")
        assert source is not None
        await session.refresh(source)
        assert source.error_count >= 1

    async def test_bedrock_fallback_on_extraction_failure(
        self, session: AsyncSession, config: AgentConfig
    ) -> None:
        """When Bedrock raises, fallback has no price so deals are skipped."""
        agent = WatchlistAgent(config=config)
        urls = ["https://amazon.com/dp/FALLBACK001"]
        tavily_results = _make_tavily_results(urls)

        with patch.object(agent, "_call_tavily", new_callable=AsyncMock, return_value=tavily_results), \
             patch("dealfinder.agents.watchlist.BedrockSearchExtractor") as MockExtractor:
            mock_extractor = MagicMock()
            mock_extractor.extract.side_effect = RuntimeError("Bedrock unavailable")
            MockExtractor.return_value = mock_extractor

            new_deals = await agent.search_query("fallback query", session)

        # Fallback results have current_price=None, so all deals are skipped
        assert len(new_deals) == 0


class TestWatchlistPriceSanityCheck:
    """Tests for WatchlistAgent._sanity_check_price."""

    async def test_suspicious_price_demoted_to_non_high_value(
        self, session: AsyncSession, config: AgentConfig
    ) -> None:
        """Deal with sale_price < 20% of estimated price should be flagged as suspicious."""
        agent = WatchlistAgent(config=config)
        # Estimated price $1500, sale price $299.99 → ratio ≈ 0.20, but let's make
        # the estimated price much higher so ratio < 0.20.
        agent._estimator = MagicMock()
        agent._estimator.estimate_price.return_value = _make_price_estimation(
            estimated_price="1999.99"
        )
        urls = ["https://amazon.com/dp/SUSPICIOUS001"]
        tavily_results = _make_tavily_results(urls)
        bedrock_results = _make_bedrock_results(urls)  # current_price=$299.99, quality=8.0

        with patch.object(agent, "_call_tavily", new_callable=AsyncMock, return_value=tavily_results), \
             patch("dealfinder.agents.watchlist.BedrockSearchExtractor") as MockExtractor:
            mock_extractor = MagicMock()
            mock_extractor.extract.return_value = bedrock_results
            MockExtractor.return_value = mock_extractor

            new_deals = await agent.search_query("overpriced item", session)

        assert len(new_deals) == 1
        deal = new_deals[0]
        assert deal.is_high_value is False
        assert deal.raw_data["price_sanity_check"]["suspicious"] is True
        assert deal.raw_data["price_sanity_check"]["estimated_price"] == 1999.99

    async def test_legitimate_deal_passes_sanity_check(
        self, session: AsyncSession, config: AgentConfig
    ) -> None:
        """Deal with a reasonable sale-to-estimated ratio passes sanity check."""
        agent = WatchlistAgent(config=config)
        agent._estimator = MagicMock()
        agent._estimator.estimate_price.return_value = _make_price_estimation(
            estimated_price="349.99"
        )
        urls = ["https://amazon.com/dp/LEGIT001"]
        tavily_results = _make_tavily_results(urls)
        bedrock_results = _make_bedrock_results(urls)  # current_price=$299.99, quality=8.0

        with patch.object(agent, "_call_tavily", new_callable=AsyncMock, return_value=tavily_results), \
             patch("dealfinder.agents.watchlist.BedrockSearchExtractor") as MockExtractor:
            mock_extractor = MagicMock()
            mock_extractor.extract.return_value = bedrock_results
            MockExtractor.return_value = mock_extractor

            new_deals = await agent.search_query("good deal", session)

        assert len(new_deals) == 1
        deal = new_deals[0]
        assert deal.is_high_value is True
        assert "price_sanity_check" in deal.raw_data
        assert "suspicious" not in deal.raw_data["price_sanity_check"]

    async def test_sanity_check_failure_keeps_high_value(
        self, session: AsyncSession, config: AgentConfig
    ) -> None:
        """When BedrockPriceEstimator raises, the deal should keep is_high_value=True."""
        agent = WatchlistAgent(config=config)
        agent._estimator = MagicMock()
        agent._estimator.estimate_price.side_effect = RuntimeError("Bedrock unavailable")
        urls = ["https://amazon.com/dp/FAILCHECK001"]
        tavily_results = _make_tavily_results(urls)
        bedrock_results = _make_bedrock_results(urls)  # quality_score=8.0 → high_value

        with patch.object(agent, "_call_tavily", new_callable=AsyncMock, return_value=tavily_results), \
             patch("dealfinder.agents.watchlist.BedrockSearchExtractor") as MockExtractor:
            mock_extractor = MagicMock()
            mock_extractor.extract.return_value = bedrock_results
            MockExtractor.return_value = mock_extractor

            new_deals = await agent.search_query("estimator fails", session)

        assert len(new_deals) == 1
        assert new_deals[0].is_high_value is True
        assert "price_sanity_check" not in new_deals[0].raw_data

    async def test_low_quality_deal_skips_sanity_check(
        self, session: AsyncSession, config: AgentConfig
    ) -> None:
        """Deals with quality_score < 7.0 should not trigger the sanity check."""
        agent = WatchlistAgent(config=config)
        agent._estimator = MagicMock()
        urls = ["https://amazon.com/dp/LOWQ001"]
        tavily_results = _make_tavily_results(urls)
        bedrock_results = [{
            "title": "Low quality deal",
            "url": urls[0],
            "current_price": "$49.99",
            "quality_score": 4.0,
            "quality_reason": "Mediocre value",
        }]

        with patch.object(agent, "_call_tavily", new_callable=AsyncMock, return_value=tavily_results), \
             patch("dealfinder.agents.watchlist.BedrockSearchExtractor") as MockExtractor:
            mock_extractor = MagicMock()
            mock_extractor.extract.return_value = bedrock_results
            MockExtractor.return_value = mock_extractor

            new_deals = await agent.search_query("low quality", session)

        assert len(new_deals) == 1
        assert new_deals[0].is_high_value is False
        agent._estimator.estimate_price.assert_not_called()


class TestWatchlistAgentHandler:
    """Tests for the Lambda handler entry point."""

    def test_handler_entry_point_returns_expected_keys(
        self, config: AgentConfig
    ) -> None:
        """Lambda handler should return dict with queries_searched, deals_discovered, scanned_at."""
        from dealfinder.agents.watchlist import handler

        with patch.object(WatchlistAgent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "queries_searched": 2,
                "deals_discovered": 5,
                "scanned_at": "2026-03-06T00:00:00+00:00",
            }
            result = handler({}, None)

        assert result["queries_searched"] == 2
        assert result["deals_discovered"] == 5
        assert "scanned_at" in result
