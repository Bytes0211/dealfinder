"""Repository pattern for data access layer.

This module provides repository classes for CRUD operations on database entities,
abstracting SQLAlchemy session management and query patterns.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dealfinder.db.connection import get_async_session
from dealfinder.db.models import (
    Deal,
    DealSource,
    DealStatus,
    Notification,
    NotificationChannel,
    NotificationStatus,
    PriceEstimate,
    User,
)

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common CRUD operations."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize repository.

        Args:
            session: Optional database session. If not provided, uses context manager.
        """
        self._session = session

    async def _get_session(self) -> AsyncSession:
        """Get database session."""
        if self._session:
            return self._session
        raise ValueError("No session provided. Use context manager or pass session.")


class DealRepository(BaseRepository):
    """Repository for Deal operations.

    Example:
        async with get_async_session() as session:
            repo = DealRepository(session)
            deal = await repo.get_by_id(deal_id)
            high_value_deals = await repo.find_high_value_deals(limit=10)
    """

    async def create(self, deal: Deal) -> Deal:
        """Create a new deal.

        Args:
            deal: Deal instance to create.

        Returns:
            Created deal with ID assigned.
        """
        session = await self._get_session()
        session.add(deal)
        await session.flush()
        await session.refresh(deal)
        logger.info(f"Created deal: {deal.id} - {deal.title}")
        return deal

    async def get_by_id(self, deal_id: UUID) -> Optional[Deal]:
        """Get deal by ID.

        Args:
            deal_id: Deal UUID.

        Returns:
            Deal instance or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(
            select(Deal)
            .where(Deal.id == deal_id)
            .options(
                selectinload(Deal.source),
                selectinload(Deal.price_estimates),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(self, source_id: UUID, external_id: str) -> Optional[Deal]:
        """Get deal by source and external ID.

        Args:
            source_id: Deal source UUID.
            external_id: External deal identifier.

        Returns:
            Deal instance or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(
            select(Deal).where(
                and_(
                    Deal.source_id == source_id,
                    Deal.external_id == external_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def find_by_status(self, status: DealStatus, limit: int = 100) -> list[Deal]:
        """Find deals by status.

        Args:
            status: Deal status to filter by.
            limit: Maximum number of results.

        Returns:
            List of deals.
        """
        session = await self._get_session()
        result = await session.execute(
            select(Deal)
            .where(Deal.status == status)
            .order_by(desc(Deal.discovered_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_high_value_deals(
        self,
        min_discount: float = 20.0,
        limit: int = 50,
    ) -> list[Deal]:
        """Find high-value deals above discount threshold.

        Args:
            min_discount: Minimum discount percentage.
            limit: Maximum number of results.

        Returns:
            List of high-value deals sorted by discount.
        """
        session = await self._get_session()
        result = await session.execute(
            select(Deal)
            .where(
                and_(
                    Deal.is_high_value == True,
                    Deal.discount_percentage >= min_discount,
                    Deal.status == DealStatus.EVALUATED,
                )
            )
            .order_by(desc(Deal.discount_percentage))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_by_category(self, category: str, limit: int = 100) -> list[Deal]:
        """Find deals by category.

        Args:
            category: Category to filter by.
            limit: Maximum number of results.

        Returns:
            List of deals in category.
        """
        session = await self._get_session()
        result = await session.execute(
            select(Deal)
            .where(Deal.category == category)
            .order_by(desc(Deal.discovered_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(self, deal_id: UUID, status: DealStatus) -> Optional[Deal]:
        """Update deal status.

        Args:
            deal_id: Deal UUID.
            status: New status.

        Returns:
            Updated deal or None if not found.
        """
        session = await self._get_session()
        deal = await self.get_by_id(deal_id)
        if deal:
            deal.status = status
            if status == DealStatus.EVALUATED:
                deal.evaluated_at = datetime.now(UTC)
            await session.flush()
            await session.refresh(deal)
            logger.info(f"Updated deal {deal_id} status to {status}")
        return deal

    async def mark_as_high_value(
        self, deal_id: UUID, estimated_value: Decimal, confidence: Decimal
    ) -> Optional[Deal]:
        """Mark deal as high value.

        Args:
            deal_id: Deal UUID.
            estimated_value: Estimated market value (Decimal to preserve Numeric precision).
            confidence: Confidence score 0–1 (Decimal to preserve Numeric precision).

        Returns:
            Updated deal or None if not found.
        """
        session = await self._get_session()
        deal = await self.get_by_id(deal_id)
        if deal:
            deal.is_high_value = True
            deal.estimated_value = estimated_value
            deal.confidence_score = confidence
            await session.flush()
            await session.refresh(deal)
            logger.info(f"Marked deal {deal_id} as high value")
        return deal

    async def count_by_status(self, status: DealStatus) -> int:
        """Count deals by status.

        Args:
            status: Deal status.

        Returns:
            Count of deals with status.
        """
        session = await self._get_session()
        result = await session.execute(
            select(func.count()).select_from(Deal).where(Deal.status == status)
        )
        return result.scalar_one()

    async def delete(self, deal_id: UUID) -> bool:
        """Delete a deal.

        Args:
            deal_id: Deal UUID.

        Returns:
            True if deleted, False if not found.
        """
        session = await self._get_session()
        deal = await self.get_by_id(deal_id)
        if deal:
            await session.delete(deal)
            logger.info(f"Deleted deal: {deal_id}")
            return True
        return False


class UserRepository(BaseRepository):
    """Repository for User operations.

    Example:
        async with get_async_session() as session:
            repo = UserRepository(session)
            user = await repo.get_by_email("user@example.com")
            active_users = await repo.find_active_users()
    """

    async def create(self, user: User) -> User:
        """Create a new user.

        Args:
            user: User instance to create.

        Returns:
            Created user with ID assigned.
        """
        session = await self._get_session()
        session.add(user)
        await session.flush()
        await session.refresh(user)
        logger.info(f"Created user: {user.id} - {user.email}")
        return user

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User UUID.

        Returns:
            User instance or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.

        Args:
            email: User email address.

        Returns:
            User instance or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username: Username.

        Returns:
            User instance or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def find_active_users(self, limit: int = 1000) -> list[User]:
        """Find all active users.

        Args:
            limit: Maximum number of results.

        Returns:
            List of active users.
        """
        session = await self._get_session()
        result = await session.execute(
            select(User).where(User.is_active == True).order_by(desc(User.created_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def update_last_login(self, user_id: UUID) -> Optional[User]:
        """Update user's last login timestamp.

        Args:
            user_id: User UUID.

        Returns:
            Updated user or None if not found.
        """
        session = await self._get_session()
        user = await self.get_by_id(user_id)
        if user:
            user.last_login_at = datetime.now(UTC)
            await session.flush()
            await session.refresh(user)
        return user

    async def update_preferences(self, user_id: UUID, preferences: dict) -> Optional[User]:
        """Update user notification preferences.

        Args:
            user_id: User UUID.
            preferences: Notification preferences dictionary.

        Returns:
            Updated user or None if not found.
        """
        session = await self._get_session()
        user = await self.get_by_id(user_id)
        if user:
            user.notification_preferences = preferences
            await session.flush()
            await session.refresh(user)
            logger.info(f"Updated preferences for user {user_id}")
        return user

    async def deactivate(self, user_id: UUID) -> Optional[User]:
        """Deactivate a user account.

        Args:
            user_id: User UUID.

        Returns:
            Updated user or None if not found.
        """
        session = await self._get_session()
        user = await self.get_by_id(user_id)
        if user:
            user.is_active = False
            await session.flush()
            await session.refresh(user)
            logger.info(f"Deactivated user: {user_id}")
        return user


class PriceEstimateRepository(BaseRepository):
    """Repository for PriceEstimate operations.

    Example:
        async with get_async_session() as session:
            repo = PriceEstimateRepository(session)
            estimates = await repo.get_by_deal_id(deal_id)
            await repo.create_estimate(deal_id, "specialist", "1.0", 599.99, 0.85)
    """

    async def create(self, estimate: PriceEstimate) -> PriceEstimate:
        """Create a new price estimate.

        Args:
            estimate: PriceEstimate instance to create.

        Returns:
            Created estimate with ID assigned.
        """
        session = await self._get_session()
        session.add(estimate)
        await session.flush()
        await session.refresh(estimate)
        logger.info(
            f"Created price estimate for deal {estimate.deal_id} from model {estimate.model_name}"
        )
        return estimate

    async def get_by_deal_id(self, deal_id: UUID) -> list[PriceEstimate]:
        """Get all price estimates for a deal.

        Args:
            deal_id: Deal UUID.

        Returns:
            List of price estimates for the deal.
        """
        session = await self._get_session()
        result = await session.execute(
            select(PriceEstimate)
            .where(PriceEstimate.deal_id == deal_id)
            .order_by(desc(PriceEstimate.created_at))
        )
        return list(result.scalars().all())

    async def get_ensemble_estimates(self, deal_id: UUID) -> list[PriceEstimate]:
        """Get ensemble member estimates for a deal.

        Args:
            deal_id: Deal UUID.

        Returns:
            List of ensemble member estimates.
        """
        session = await self._get_session()
        result = await session.execute(
            select(PriceEstimate).where(
                and_(
                    PriceEstimate.deal_id == deal_id,
                    PriceEstimate.is_ensemble_member == True,
                )
            )
        )
        return list(result.scalars().all())

    async def get_by_model(
        self, deal_id: UUID, model_name: str, model_version: str
    ) -> Optional[PriceEstimate]:
        """Get estimate by model name and version.

        Args:
            deal_id: Deal UUID.
            model_name: Model name.
            model_version: Model version.

        Returns:
            Price estimate or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(
            select(PriceEstimate).where(
                and_(
                    PriceEstimate.deal_id == deal_id,
                    PriceEstimate.model_name == model_name,
                    PriceEstimate.model_version == model_version,
                )
            )
        )
        return result.scalar_one_or_none()


class DealSourceRepository(BaseRepository):
    """Repository for DealSource operations.

    Example:
        async with get_async_session() as session:
            repo = DealSourceRepository(session)
            sources = await repo.find_active_sources()
            await repo.update_check_time(source_id)
    """

    async def create(self, source: DealSource) -> DealSource:
        """Create a new deal source.

        Args:
            source: DealSource instance to create.

        Returns:
            Created source with ID assigned.
        """
        session = await self._get_session()
        session.add(source)
        await session.flush()
        await session.refresh(source)
        logger.info(f"Created deal source: {source.id} - {source.name}")
        return source

    async def get_by_id(self, source_id: UUID) -> Optional[DealSource]:
        """Get source by ID.

        Args:
            source_id: Source UUID.

        Returns:
            DealSource instance or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(select(DealSource).where(DealSource.id == source_id))
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Optional[DealSource]:
        """Get source by URL.

        Args:
            url: Source URL.

        Returns:
            DealSource instance or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(select(DealSource).where(DealSource.url == url))
        return result.scalar_one_or_none()

    async def find_active_sources(self) -> list[DealSource]:
        """Find all active sources.

        Returns:
            List of active deal sources.
        """
        session = await self._get_session()
        result = await session.execute(
            select(DealSource).where(DealSource.is_active == True).order_by(DealSource.name)
        )
        return list(result.scalars().all())

    async def update_check_time(
        self, source_id: UUID, success: bool = True
    ) -> Optional[DealSource]:
        """Update source check timestamp.

        Args:
            source_id: Source UUID.
            success: Whether the check was successful.

        Returns:
            Updated source or None if not found.
        """
        session = await self._get_session()
        source = await self.get_by_id(source_id)
        if source:
            source.last_checked_at = datetime.now(UTC)
            if success:
                source.last_successful_at = datetime.now(UTC)
                source.error_count = 0
            else:
                source.error_count += 1
            await session.flush()
            await session.refresh(source)
        return source


class NotificationRepository(BaseRepository):
    """Repository for Notification operations.

    Example:
        async with get_async_session() as session:
            repo = NotificationRepository(session)
            await repo.create_notification(user_id, deal_id, "email", "New Deal!", "...")
            pending = await repo.find_pending_notifications()
    """

    async def create(self, notification: Notification) -> Notification:
        """Create a new notification.

        Args:
            notification: Notification instance to create.

        Returns:
            Created notification with ID assigned.
        """
        session = await self._get_session()
        session.add(notification)
        await session.flush()
        await session.refresh(notification)
        logger.info(
            f"Created notification for user {notification.user_id} via {notification.channel}"
        )
        return notification

    async def find_pending_notifications(
        self, channel: Optional[NotificationChannel] = None, limit: int = 100
    ) -> list[Notification]:
        """Find pending notifications.

        Args:
            channel: Optional channel filter.
            limit: Maximum number of results.

        Returns:
            List of pending notifications.
        """
        session = await self._get_session()
        query = select(Notification).where(Notification.status == NotificationStatus.PENDING)
        if channel:
            query = query.where(Notification.channel == channel)
        query = query.order_by(Notification.created_at).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    async def mark_as_sent(
        self, notification_id: UUID, external_id: Optional[str] = None
    ) -> Optional[Notification]:
        """Mark notification as sent.

        Args:
            notification_id: Notification UUID.
            external_id: External message ID from service.

        Returns:
            Updated notification or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification:
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.now(UTC)
            if external_id:
                notification.external_message_id = external_id
            await session.flush()
            await session.refresh(notification)
        return notification

    async def mark_as_failed(
        self, notification_id: UUID, error_message: str
    ) -> Optional[Notification]:
        """Mark notification as failed.

        Args:
            notification_id: Notification UUID.
            error_message: Error description.

        Returns:
            Updated notification or None if not found.
        """
        session = await self._get_session()
        result = await session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification:
            notification.status = NotificationStatus.FAILED
            notification.error_message = error_message
            notification.retry_count += 1
            await session.flush()
            await session.refresh(notification)
        return notification
