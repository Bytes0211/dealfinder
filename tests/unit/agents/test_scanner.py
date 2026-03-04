"""Unit tests for ScannerAgent.

Uses an in-memory SQLite database and mocked feedparser to exercise
deal persistence logic without network or real database dependencies.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

# Register PostgreSQL types for SQLite compatibility
@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    """Render JSONB as JSON for SQLite."""
    return "JSON"


@compiles(PGUUID, "sqlite")
def _pguuid_sqlite(type_, compiler, **kw):
    """Render PostgreSQL UUID as CHAR(32) for SQLite."""
    return "CHAR(32)"


from dealfinder.agents.config import AgentConfig
from dealfinder.agents.scanner import ScannerAgent
from dealfinder.data.repository import DealRepository, DealSourceRepository
from dealfinder.db.models import Base, DealSource, DealStatus


def _make_feed_entry(id_: str, title: str, link: str, summary: str = "") -> MagicMock:
    """Create a minimal feedparser-style entry object."""
    entry = MagicMock()
    entry.get = lambda key, default=None: {
        "id": id_,
        "title": title,
        "link": link,
        "summary": summary,
        "published": "Mon, 01 Jan 2026 00:00:00 +0000",
        "tags": [],
    }.get(key, default)
    return entry


def _make_feed(entries: list, bozo: bool = False) -> MagicMock:
    """Create a minimal feedparser-style feed object."""
    feed = MagicMock()
    feed.entries = entries
    feed.bozo = bozo
    feed.bozo_exception = Exception("parse error") if bozo else None
    return feed


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
    """Open database session."""
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest.fixture
async def source(session) -> DealSource:
    """Persisted active DealSource."""
    src = DealSource(
        name="Test Feed",
        url="https://example.com/feed.rss",
        category="electronics",
        is_active=True,
    )
    session.add(src)
    await session.commit()
    await session.refresh(src)
    return src


@pytest.fixture
def config() -> AgentConfig:
    """Agent config with test values."""
    return AgentConfig(
        discount_threshold=20.0,
        bedrock_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        notification_queue_url="",
    )


class TestScannerAgentScanSource:
    """Tests for ScannerAgent.scan_source."""

    async def test_creates_new_deals_from_feed(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """New feed entries should be persisted as DISCOVERED deals."""
        entries = [
            _make_feed_entry("entry-1", "Laptop Deal", "https://example.com/1"),
            _make_feed_entry("entry-2", "Phone Deal", "https://example.com/2"),
        ]
        feed = _make_feed(entries)

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            new_deals = await agent.scan_source(source, session)

        assert len(new_deals) == 2
        titles = {d.title for d in new_deals}
        assert titles == {"Laptop Deal", "Phone Deal"}
        for deal in new_deals:
            assert deal.status == DealStatus.DISCOVERED
            assert deal.source_id == source.id

    async def test_skips_duplicate_deals(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """Feed entries already in the database should not be re-created."""
        entries = [_make_feed_entry("entry-1", "Existing Deal", "https://example.com/1")]
        feed = _make_feed(entries)

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            # First scan — should create 1 deal
            first = await agent.scan_source(source, session)
            await session.commit()

            # Second scan with same feed — should create 0 new deals
            second = await agent.scan_source(source, session)

        assert len(first) == 1
        assert len(second) == 0

    async def test_handles_bozo_feed_with_no_entries(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """A bozo feed with no entries should return empty list and mark source as failed."""
        feed = _make_feed(entries=[], bozo=True)

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            new_deals = await agent.scan_source(source, session)

        assert new_deals == []

        # Source error count should be incremented
        await session.refresh(source)
        assert source.error_count == 1

    async def test_stores_raw_data_on_deal(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """Raw feed entry data should be stored in the deal's raw_data field."""
        entries = [_make_feed_entry("entry-1", "Widget Deal", "https://example.com/w")]
        feed = _make_feed(entries)

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            deals = await agent.scan_source(source, session)

        assert len(deals) == 1
        assert deals[0].raw_data is not None
        assert deals[0].raw_data["title"] == "Widget Deal"
        assert deals[0].raw_data["link"] == "https://example.com/w"

    async def test_truncates_long_title(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """Titles longer than 500 characters should be truncated."""
        long_title = "A" * 600
        entries = [_make_feed_entry("entry-1", long_title, "https://example.com/long")]
        feed = _make_feed(entries)

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            deals = await agent.scan_source(source, session)

        assert len(deals[0].title) <= 500

    async def test_updates_source_check_time_on_success(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """Successful scan should set last_checked_at and last_successful_at."""
        feed = _make_feed(entries=[])

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            await agent.scan_source(source, session)
        await session.commit()

        await session.refresh(source)
        assert source.last_checked_at is not None
        assert source.last_successful_at is not None
        assert source.error_count == 0

    async def test_returns_empty_on_exception(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """An unexpected exception during feed parsing should return empty list."""
        agent = ScannerAgent(config=config)
        with patch(
            "dealfinder.agents.scanner.feedparser.parse",
            side_effect=ConnectionError("timeout"),
        ):
            deals = await agent.scan_source(source, session)

        assert deals == []
