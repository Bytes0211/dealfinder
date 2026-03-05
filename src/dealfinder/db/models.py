"""SQLAlchemy ORM models for Deal Finder.

This module defines the database schema for:
- Deals: Discovered deals from RSS feeds
- Users: User accounts and preferences
- PriceEstimates: ML model price predictions
- DealSources: RSS feed sources
- Notifications: Notification history
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class DealStatus(str, Enum):
    """Status of a deal in the processing pipeline."""

    DISCOVERED = "discovered"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    NOTIFIED = "notified"
    EXPIRED = "expired"
    REJECTED = "rejected"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""

    EMAIL = "email"
    SNS = "sns"
    SMS = "sms"
    WEBSOCKET = "websocket"


class NotificationStatus(str, Enum):
    """Status of a notification."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class DealSource(Base):
    """RSS feed sources for deal discovery."""

    __tablename__ = "deal_sources"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_successful_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    deals: Mapped[list["Deal"]] = relationship("Deal", back_populates="source")

    __table_args__ = (
        Index("ix_deal_sources_is_active", "is_active"),
        Index("ix_deal_sources_category", "category"),
    )


class Deal(Base):
    """Discovered deals from RSS feeds."""

    __tablename__ = "deals"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("deal_sources.id"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    
    # Pricing
    original_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    sale_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    estimated_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    
    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(100))
    brand: Mapped[Optional[str]] = mapped_column(String(255))
    tags: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    
    # Status and processing
    status: Mapped[DealStatus] = mapped_column(
        SQLEnum(DealStatus), default=DealStatus.DISCOVERED
    )
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    is_high_value: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Vector search
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Timestamps
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Raw data
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    source: Mapped["DealSource"] = relationship("DealSource", back_populates="deals")
    price_estimates: Mapped[list["PriceEstimate"]] = relationship(
        "PriceEstimate", back_populates="deal", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="deal", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_deals_source_external"),
        Index("ix_deals_status", "status"),
        Index("ix_deals_is_high_value", "is_high_value"),
        Index("ix_deals_discovered_at", "discovered_at"),
        Index("ix_deals_category", "category"),
        Index("ix_deals_discount_percentage", "discount_percentage"),
    )


class User(Base):
    """User accounts and preferences."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Profile
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Preferences
    notification_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    discount_threshold: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("20.00")
    )
    preferred_categories: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    
    # External integrations
    
    # Timestamps
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="user"
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_is_active", "is_active"),
    )


class PriceEstimate(Base):
    """ML model price predictions for deals."""

    __tablename__ = "price_estimates"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    deal_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    
    # Model identification
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Prediction
    estimated_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    prediction_range_low: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    prediction_range_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    
    # Ensemble weighting
    ensemble_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3))
    is_ensemble_member: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Metadata
    inference_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    features_used: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    deal: Mapped["Deal"] = relationship("Deal", back_populates="price_estimates")

    __table_args__ = (
        Index("ix_price_estimates_deal_id", "deal_id"),
        Index("ix_price_estimates_model_name", "model_name"),
        UniqueConstraint(
            "deal_id", "model_name", "model_version",
            name="uq_price_estimates_deal_model"
        ),
    )


class Notification(Base):
    """Notification history."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    deal_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False
    )
    
    # Delivery
    channel: Mapped[NotificationChannel] = mapped_column(
        SQLEnum(NotificationChannel), nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus), default=NotificationStatus.PENDING
    )
    
    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Delivery tracking
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # External references
    external_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    deal: Mapped["Deal"] = relationship("Deal", back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_deal_id", "deal_id"),
        Index("ix_notifications_status", "status"),
        Index("ix_notifications_channel", "channel"),
    )
