"""Unit tests for database models."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

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


class TestDealStatus:
    """Tests for DealStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert DealStatus.DISCOVERED == "discovered"
        assert DealStatus.EVALUATING == "evaluating"
        assert DealStatus.EVALUATED == "evaluated"
        assert DealStatus.NOTIFIED == "notified"
        assert DealStatus.EXPIRED == "expired"
        assert DealStatus.REJECTED == "rejected"

    def test_status_is_string(self):
        """Test status values are strings."""
        for status in DealStatus:
            assert isinstance(status.value, str)


class TestNotificationChannel:
    """Tests for NotificationChannel enum."""

    def test_channel_values(self):
        """Test all channel values exist."""
        assert NotificationChannel.EMAIL == "email"
        assert NotificationChannel.SNS == "sns"
        assert NotificationChannel.SMS == "sms"
        assert NotificationChannel.WEBSOCKET == "websocket"


class TestNotificationStatus:
    """Tests for NotificationStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert NotificationStatus.PENDING == "pending"
        assert NotificationStatus.SENT == "sent"
        assert NotificationStatus.DELIVERED == "delivered"
        assert NotificationStatus.FAILED == "failed"


class TestDealSourceModel:
    """Tests for DealSource model."""

    def test_create_deal_source(self):
        """Test creating a DealSource instance."""
        source = DealSource(
            name="Test Source",
            url="https://example.com/feed.rss",
            category="electronics",
            is_active=True,
            check_interval_minutes=15,
        )

        assert source.name == "Test Source"
        assert source.url == "https://example.com/feed.rss"
        assert source.category == "electronics"
        assert source.is_active is True
        assert source.check_interval_minutes == 15

    def test_deal_source_defaults(self):
        """Test DealSource default values are defined in the model."""
        # Note: SQLAlchemy defaults are applied at insert time, not instantiation
        # We test that the column has a default defined
        from sqlalchemy import inspect
        mapper = inspect(DealSource)
        
        is_active_col = mapper.columns["is_active"]
        check_interval_col = mapper.columns["check_interval_minutes"]
        error_count_col = mapper.columns["error_count"]
        
        assert is_active_col.default is not None
        assert check_interval_col.default is not None
        assert error_count_col.default is not None

    def test_deal_source_tablename(self):
        """Test table name is correct."""
        assert DealSource.__tablename__ == "deal_sources"


class TestDealModel:
    """Tests for Deal model."""

    def test_create_deal(self):
        """Test creating a Deal instance."""
        source_id = uuid4()
        deal = Deal(
            source_id=source_id,
            external_id="ext-123",
            title="Great Laptop Deal",
            description="50% off laptops",
            url="https://example.com/deal",
            original_price=Decimal("999.99"),
            sale_price=Decimal("499.99"),
            discount_percentage=Decimal("50.00"),
            category="electronics",
            brand="TechBrand",
        )

        assert deal.source_id == source_id
        assert deal.external_id == "ext-123"
        assert deal.title == "Great Laptop Deal"
        assert deal.original_price == Decimal("999.99")
        assert deal.sale_price == Decimal("499.99")
        assert deal.discount_percentage == Decimal("50.00")

    def test_deal_defaults(self):
        """Test Deal default values are defined in the model."""
        from sqlalchemy import inspect
        mapper = inspect(Deal)
        
        status_col = mapper.columns["status"]
        is_high_value_col = mapper.columns["is_high_value"]
        currency_col = mapper.columns["currency"]
        
        assert status_col.default is not None
        assert is_high_value_col.default is not None
        assert currency_col.default is not None

    def test_deal_tablename(self):
        """Test table name is correct."""
        assert Deal.__tablename__ == "deals"


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self):
        """Test creating a User instance."""
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password="hashedpassword123",
            full_name="Test User",
        )

        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.hashed_password == "hashedpassword123"
        assert user.full_name == "Test User"

    def test_user_defaults(self):
        """Test User default values are defined in the model."""
        from sqlalchemy import inspect
        mapper = inspect(User)
        
        is_active_col = mapper.columns["is_active"]
        is_verified_col = mapper.columns["is_verified"]
        discount_threshold_col = mapper.columns["discount_threshold"]
        
        assert is_active_col.default is not None
        assert is_verified_col.default is not None
        assert discount_threshold_col.default is not None

    def test_user_tablename(self):
        """Test table name is correct."""
        assert User.__tablename__ == "users"


class TestPriceEstimateModel:
    """Tests for PriceEstimate model."""

    def test_create_price_estimate(self):
        """Test creating a PriceEstimate instance."""
        deal_id = uuid4()
        estimate = PriceEstimate(
            deal_id=deal_id,
            model_name="specialist",
            model_version="1.0.0",
            estimated_price=Decimal("599.99"),
            confidence=Decimal("0.85"),
            inference_time_ms=150,
        )

        assert estimate.deal_id == deal_id
        assert estimate.model_name == "specialist"
        assert estimate.model_version == "1.0.0"
        assert estimate.estimated_price == Decimal("599.99")
        assert estimate.confidence == Decimal("0.85")

    def test_price_estimate_defaults(self):
        """Test PriceEstimate default values are defined in the model."""
        from sqlalchemy import inspect
        mapper = inspect(PriceEstimate)
        
        is_ensemble_member_col = mapper.columns["is_ensemble_member"]
        
        assert is_ensemble_member_col.default is not None

    def test_price_estimate_tablename(self):
        """Test table name is correct."""
        assert PriceEstimate.__tablename__ == "price_estimates"


class TestNotificationModel:
    """Tests for Notification model."""

    def test_create_notification(self):
        """Test creating a Notification instance."""
        user_id = uuid4()
        deal_id = uuid4()
        notification = Notification(
            user_id=user_id,
            deal_id=deal_id,
            channel=NotificationChannel.EMAIL,
            title="New Deal Alert",
            message="Check out this great deal!",
        )

        assert notification.user_id == user_id
        assert notification.deal_id == deal_id
        assert notification.channel == NotificationChannel.EMAIL
        assert notification.title == "New Deal Alert"

    def test_notification_defaults(self):
        """Test Notification default values are defined in the model."""
        from sqlalchemy import inspect
        mapper = inspect(Notification)
        
        status_col = mapper.columns["status"]
        retry_count_col = mapper.columns["retry_count"]
        
        assert status_col.default is not None
        assert retry_count_col.default is not None

    def test_notification_tablename(self):
        """Test table name is correct."""
        assert Notification.__tablename__ == "notifications"


class TestBase:
    """Tests for Base declarative class."""

    def test_base_is_declarative_base(self):
        """Test Base is a declarative base."""
        from sqlalchemy.orm import DeclarativeBase
        assert issubclass(Base, DeclarativeBase)

    def test_all_models_inherit_from_base(self):
        """Test all models inherit from Base."""
        assert issubclass(Deal, Base)
        assert issubclass(DealSource, Base)
        assert issubclass(User, Base)
        assert issubclass(PriceEstimate, Base)
        assert issubclass(Notification, Base)
