"""Unit tests for ScannerAgent.

Uses an in-memory SQLite database and mocked feedparser to exercise
deal persistence logic without network or real database dependencies.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

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

    async def test_link_used_as_external_id_when_entry_has_no_id(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """Entries with no RSS id should fall back to link for deduplication.

        The external_id priority is: id > link > sha256 hash. When id is absent
        but a link is present, the link is used so the entry is still persisted
        and correctly deduplicated on subsequent scans.
        """
        entry = MagicMock()
        entry.get = lambda key, default=None: {
            "id": None,
            "title": "No-ID Widget",
            "link": "https://example.com/no-id-widget",
            "summary": "",
            "published": "Mon, 01 Jan 2026 00:00:00 +0000",
            "tags": [],
        }.get(key, default)
        feed = _make_feed([entry])

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            first = await agent.scan_source(source, session)
            await session.commit()
            second = await agent.scan_source(source, session)

        assert len(first) == 1, "First scan should create one deal"
        assert len(second) == 0, "Second scan should skip — same link used as external_id"

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

    async def test_skips_entries_with_no_url(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """Feed entries with no link should be silently skipped.

        Storing an empty string as url is misleading for downstream consumers;
        entries without a URL are simply omitted from the results.
        """
        entry_no_url = MagicMock()
        entry_no_url.get = lambda key, default=None: {
            "id": "entry-no-link",
            "title": "Linkless Deal",
            "link": None,
            "summary": "",
            "published": "Mon, 01 Jan 2026 00:00:00 +0000",
            "tags": [],
        }.get(key, default)
        entry_with_url = _make_feed_entry("entry-1", "Good Deal", "https://example.com/1")
        feed = _make_feed([entry_no_url, entry_with_url])

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            deals = await agent.scan_source(source, session)

        assert len(deals) == 1
        assert deals[0].title == "Good Deal"

    async def test_check_time_failure_does_not_suppress_new_deals(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """A failure in update_check_time(success=True) must not suppress deal IDs.

        Before the fix, an exception from update_check_time(success=True) escaped
        to the outer except, which returned [] even though the deals had already
        been queued in the session via savepoints.
        """
        entries = [_make_feed_entry("entry-1", "Good Deal", "https://example.com/1")]
        feed = _make_feed(entries)

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            with patch.object(
                DealSourceRepository,
                "update_check_time",
                new_callable=AsyncMock,
                side_effect=RuntimeError("health counter failure"),
            ):
                deals = await agent.scan_source(source, session)

        assert len(deals) == 1
        assert deals[0].title == "Good Deal"

    async def test_db_error_during_create_still_updates_source_health(
        self, session, source: DealSource, config: AgentConfig
    ) -> None:
        """A race-condition DB constraint error during create() is isolated by a
        savepoint so it does not poison the session or prevent health counters
        from being updated.

        Before the fix, an IntegrityError from deal_repo.create() deactivated
        the asyncpg transaction, causing update_check_time to raise
        PendingRollbackError.  The savepoint wrapping each insert rolls back only
        that entry, leaving the session healthy.  The duplicate is silently
        skipped and the source health counters reflect a successful scan
        (success=True because the feed itself was processed).
        """
        from dealfinder.db.models import Deal as DealModel

        # Pre-insert a deal that will cause a UNIQUE constraint violation
        duplicate = DealModel(
            source_id=source.id,
            external_id="entry-dup",
            title="Pre-existing Deal",
            url="https://example.com/dup",
            status=DealStatus.DISCOVERED,
        )
        session.add(duplicate)
        await session.commit()

        # Feed returns an entry with the same external_id
        entries = [_make_feed_entry("entry-dup", "New Deal", "https://example.com/dup")]
        feed = _make_feed(entries)

        agent = ScannerAgent(config=config)
        with patch("dealfinder.agents.scanner.feedparser.parse", return_value=feed):
            # Bypass the duplicate check so create() is actually attempted and
            # hits the real UNIQUE constraint.  The savepoint rolls back only
            # this entry; the session remains healthy for update_check_time.
            with patch.object(
                DealRepository, "get_by_external_id", new_callable=AsyncMock, return_value=None
            ):
                deals = await agent.scan_source(source, session)

        # Duplicate was skipped; scan completed with success=True
        assert deals == []
        await session.refresh(source)
        assert source.last_successful_at is not None  # update_check_time ran OK
        assert source.error_count == 0  # success=True path, not error path
