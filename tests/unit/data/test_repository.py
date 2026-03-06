"""Unit tests for repository pattern."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker


# Register PostgreSQL types for SQLite compilation so in-memory tests work.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    """Render JSONB as JSON for SQLite."""
    return "JSON"


@compiles(PGUUID, "sqlite")
def _compile_pguuid_sqlite(type_, compiler, **kw):
    """Render PostgreSQL UUID as CHAR(32) for SQLite."""
    return "CHAR(32)"

from dealfinder.data.repository import (
    DealRepository,
    DealSourceRepository,
    NotificationRepository,
    PriceEstimateRepository,
    UserRepository,
)
from dealfinder.db.models import (
    Base,
    Deal,
    DealSource,
    DealStatus,
    Notification,
    NotificationChannel,
    NotificationStatus,
    PriceEstimate,
    User,
)


@pytest.fixture
async def engine():
    """Create in-memory SQLite engine for testing.

    Registers PostgreSQL-specific types (JSONB, UUID) as SQLite-compatible
    equivalents so that ORM models compile correctly against SQLite.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        """Enable WAL mode and foreign keys for SQLite."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def session(engine):
    """Create database session for testing."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session


@pytest.fixture
async def sample_source(session):
    """Create sample deal source."""
    source = DealSource(
        name="Test Source",
        url="https://example.com/feed.rss",
        is_active=True,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return source


@pytest.fixture
async def sample_user(session):
    """Create sample user."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password="hashedpass123",
        full_name="Test User",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def sample_deal(session, sample_source):
    """Create sample deal."""
    deal = Deal(
        source_id=sample_source.id,
        external_id="ext-123",
        title="Great Laptop Deal",
        description="50% off laptops",
        url="https://example.com/deal",
        original_price=Decimal("999.99"),
        sale_price=Decimal("499.99"),
        discount_percentage=Decimal("50.00"),
        status=DealStatus.DISCOVERED,
    )
    session.add(deal)
    await session.commit()
    await session.refresh(deal)
    return deal


class TestDealRepository:
    """Tests for DealRepository."""

    @pytest.mark.asyncio
    async def test_create_deal(self, session, sample_source):
        """Test creating a new deal."""
        repo = DealRepository(session)

        deal = Deal(
            source_id=sample_source.id,
            external_id="new-deal",
            title="New Deal",
            url="https://example.com/new",
        )

        created = await repo.create(deal)

        assert created.id is not None
        assert created.title == "New Deal"
        assert created.status == DealStatus.DISCOVERED

    @pytest.mark.asyncio
    async def test_get_by_id(self, session, sample_deal):
        """Test getting deal by ID."""
        repo = DealRepository(session)

        result = await repo.get_by_id(sample_deal.id)

        assert result is not None
        assert result.id == sample_deal.id
        assert result.title == sample_deal.title

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, session):
        """Test getting non-existent deal."""
        repo = DealRepository(session)

        result = await repo.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_external_id(self, session, sample_source, sample_deal):
        """Test getting deal by external ID."""
        repo = DealRepository(session)

        result = await repo.get_by_external_id(sample_source.id, "ext-123")

        assert result is not None
        assert result.id == sample_deal.id

    @pytest.mark.asyncio
    async def test_find_by_status(self, session, sample_deal):
        """Test finding deals by status."""
        repo = DealRepository(session)

        results = await repo.find_by_status(DealStatus.DISCOVERED)

        assert len(results) == 1
        assert results[0].id == sample_deal.id

    @pytest.mark.asyncio
    async def test_find_high_value_deals(self, session, sample_source):
        """Test finding high-value deals."""
        repo = DealRepository(session)

        # Create high-value deal
        high_value_deal = Deal(
            source_id=sample_source.id,
            external_id="high-value",
            title="High Value Deal",
            url="https://example.com/high",
            is_high_value=True,
            discount_percentage=Decimal("60.00"),
            status=DealStatus.EVALUATED,
        )
        session.add(high_value_deal)
        await session.commit()

        results = await repo.find_high_value_deals(min_discount=50.0)

        assert len(results) == 1
        assert results[0].id == high_value_deal.id

    @pytest.mark.asyncio
    async def test_update_status(self, session, sample_deal):
        """Test updating deal status."""
        repo = DealRepository(session)

        updated = await repo.update_status(sample_deal.id, DealStatus.EVALUATED)

        assert updated is not None
        assert updated.status == DealStatus.EVALUATED
        assert updated.evaluated_at is not None

    @pytest.mark.asyncio
    async def test_mark_as_high_value(self, session, sample_deal):
        """Test marking deal as high value."""
        repo = DealRepository(session)

        updated = await repo.mark_as_high_value(sample_deal.id, 599.99, 0.85)

        assert updated is not None
        assert updated.is_high_value is True
        assert updated.estimated_value == Decimal("599.99")
        assert updated.confidence_score == Decimal("0.85")

    @pytest.mark.asyncio
    async def test_count_by_status(self, session, sample_deal):
        """Test counting deals by status."""
        repo = DealRepository(session)

        count = await repo.count_by_status(DealStatus.DISCOVERED)

        assert count == 1

    @pytest.mark.asyncio
    async def test_delete_deal(self, session, sample_deal):
        """Test deleting a deal."""
        repo = DealRepository(session)

        deleted = await repo.delete(sample_deal.id)

        assert deleted is True

        # Verify deletion
        result = await repo.get_by_id(sample_deal.id)
        assert result is None


class TestUserRepository:
    """Tests for UserRepository."""

    @pytest.mark.asyncio
    async def test_create_user(self, session):
        """Test creating a new user."""
        repo = UserRepository(session)

        user = User(
            email="new@example.com",
            username="newuser",
            hashed_password="hashed",
        )

        created = await repo.create(user)

        assert created.id is not None
        assert created.email == "new@example.com"
        assert created.is_active is True

    @pytest.mark.asyncio
    async def test_get_by_email(self, session, sample_user):
        """Test getting user by email."""
        repo = UserRepository(session)

        result = await repo.get_by_email("test@example.com")

        assert result is not None
        assert result.id == sample_user.id

    @pytest.mark.asyncio
    async def test_get_by_username(self, session, sample_user):
        """Test getting user by username."""
        repo = UserRepository(session)

        result = await repo.get_by_username("testuser")

        assert result is not None
        assert result.id == sample_user.id

    @pytest.mark.asyncio
    async def test_find_active_users(self, session, sample_user):
        """Test finding active users."""
        repo = UserRepository(session)

        results = await repo.find_active_users()

        assert len(results) == 1
        assert results[0].id == sample_user.id

    @pytest.mark.asyncio
    async def test_update_last_login(self, session, sample_user):
        """Test updating last login timestamp."""
        repo = UserRepository(session)

        updated = await repo.update_last_login(sample_user.id)

        assert updated is not None
        assert updated.last_login_at is not None

    @pytest.mark.asyncio
    async def test_update_preferences(self, session, sample_user):
        """Test updating notification preferences."""
        repo = UserRepository(session)

        preferences = {"email": True, "pushover": False}
        updated = await repo.update_preferences(sample_user.id, preferences)

        assert updated is not None
        assert updated.notification_preferences == preferences

    @pytest.mark.asyncio
    async def test_deactivate_user(self, session, sample_user):
        """Test deactivating a user."""
        repo = UserRepository(session)

        updated = await repo.deactivate(sample_user.id)

        assert updated is not None
        assert updated.is_active is False


class TestPriceEstimateRepository:
    """Tests for PriceEstimateRepository."""

    @pytest.mark.asyncio
    async def test_create_estimate(self, session, sample_deal):
        """Test creating a price estimate."""
        repo = PriceEstimateRepository(session)

        estimate = PriceEstimate(
            deal_id=sample_deal.id,
            model_name="specialist",
            model_version="1.0.0",
            estimated_price=Decimal("599.99"),
            confidence=Decimal("0.85"),
        )

        created = await repo.create(estimate)

        assert created.id is not None
        assert created.model_name == "specialist"

    @pytest.mark.asyncio
    async def test_get_by_deal_id(self, session, sample_deal):
        """Test getting estimates by deal ID."""
        repo = PriceEstimateRepository(session)

        # Create estimate
        estimate = PriceEstimate(
            deal_id=sample_deal.id,
            model_name="specialist",
            model_version="1.0.0",
            estimated_price=Decimal("599.99"),
            confidence=Decimal("0.85"),
        )
        session.add(estimate)
        await session.commit()

        results = await repo.get_by_deal_id(sample_deal.id)

        assert len(results) == 1
        assert results[0].deal_id == sample_deal.id

    @pytest.mark.asyncio
    async def test_get_ensemble_estimates(self, session, sample_deal):
        """Test getting ensemble member estimates."""
        repo = PriceEstimateRepository(session)

        # Create ensemble estimate
        estimate = PriceEstimate(
            deal_id=sample_deal.id,
            model_name="specialist",
            model_version="1.0.0",
            estimated_price=Decimal("599.99"),
            confidence=Decimal("0.85"),
            is_ensemble_member=True,
        )
        session.add(estimate)
        await session.commit()

        results = await repo.get_ensemble_estimates(sample_deal.id)

        assert len(results) == 1
        assert results[0].is_ensemble_member is True

    @pytest.mark.asyncio
    async def test_get_by_model(self, session, sample_deal):
        """Test getting estimate by model name and version."""
        repo = PriceEstimateRepository(session)

        # Create estimate
        estimate = PriceEstimate(
            deal_id=sample_deal.id,
            model_name="specialist",
            model_version="1.0.0",
            estimated_price=Decimal("599.99"),
            confidence=Decimal("0.85"),
        )
        session.add(estimate)
        await session.commit()

        result = await repo.get_by_model(sample_deal.id, "specialist", "1.0.0")

        assert result is not None
        assert result.model_name == "specialist"


class TestDealSourceRepository:
    """Tests for DealSourceRepository."""

    @pytest.mark.asyncio
    async def test_create_source(self, session):
        """Test creating a deal source."""
        repo = DealSourceRepository(session)

        source = DealSource(
            name="New Source",
            url="https://example.com/new-feed",
        )

        created = await repo.create(source)

        assert created.id is not None
        assert created.name == "New Source"

    @pytest.mark.asyncio
    async def test_get_by_url(self, session, sample_source):
        """Test getting source by URL."""
        repo = DealSourceRepository(session)

        result = await repo.get_by_url("https://example.com/feed.rss")

        assert result is not None
        assert result.id == sample_source.id

    @pytest.mark.asyncio
    async def test_find_active_sources(self, session, sample_source):
        """Test finding active sources."""
        repo = DealSourceRepository(session)

        results = await repo.find_active_sources()

        assert len(results) == 1
        assert results[0].id == sample_source.id

    @pytest.mark.asyncio
    async def test_update_check_time(self, session, sample_source):
        """Test updating check time."""
        repo = DealSourceRepository(session)

        updated = await repo.update_check_time(sample_source.id, success=True)

        assert updated is not None
        assert updated.last_checked_at is not None
        assert updated.last_successful_at is not None
        assert updated.error_count == 0


class TestNotificationRepository:
    """Tests for NotificationRepository."""

    @pytest.mark.asyncio
    async def test_create_notification(self, session, sample_user, sample_deal):
        """Test creating a notification."""
        repo = NotificationRepository(session)

        notification = Notification(
            user_id=sample_user.id,
            deal_id=sample_deal.id,
            channel=NotificationChannel.EMAIL,
            title="New Deal Alert",
            message="Check out this deal!",
        )

        created = await repo.create(notification)

        assert created.id is not None
        assert created.status == NotificationStatus.PENDING

    @pytest.mark.asyncio
    async def test_find_pending_notifications(self, session, sample_user, sample_deal):
        """Test finding pending notifications."""
        repo = NotificationRepository(session)

        # Create pending notification
        notification = Notification(
            user_id=sample_user.id,
            deal_id=sample_deal.id,
            channel=NotificationChannel.EMAIL,
            title="Test",
            message="Test",
            status=NotificationStatus.PENDING,
        )
        session.add(notification)
        await session.commit()

        results = await repo.find_pending_notifications()

        assert len(results) == 1
        assert results[0].status == NotificationStatus.PENDING

    @pytest.mark.asyncio
    async def test_mark_as_sent(self, session, sample_user, sample_deal):
        """Test marking notification as sent."""
        repo = NotificationRepository(session)

        # Create notification
        notification = Notification(
            user_id=sample_user.id,
            deal_id=sample_deal.id,
            channel=NotificationChannel.EMAIL,
            title="Test",
            message="Test",
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)

        updated = await repo.mark_as_sent(notification.id, "ext-msg-123")

        assert updated is not None
        assert updated.status == NotificationStatus.SENT
        assert updated.sent_at is not None
        assert updated.external_message_id == "ext-msg-123"

    @pytest.mark.asyncio
    async def test_mark_as_failed(self, session, sample_user, sample_deal):
        """Test marking notification as failed."""
        repo = NotificationRepository(session)

        # Create notification
        notification = Notification(
            user_id=sample_user.id,
            deal_id=sample_deal.id,
            channel=NotificationChannel.EMAIL,
            title="Test",
            message="Test",
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)

        updated = await repo.mark_as_failed(notification.id, "Failed to send")

        assert updated is not None
        assert updated.status == NotificationStatus.FAILED
        assert updated.error_message == "Failed to send"
        assert updated.retry_count == 1
