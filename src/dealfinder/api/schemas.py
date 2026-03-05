"""Pydantic request/response schemas for the Deal Finder API.

All schemas use snake_case field names matching the ORM models.
UUID fields are serialised as strings for JSON compatibility.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ─────────────────────────────────────────────
# Deal schemas
# ─────────────────────────────────────────────


class DealResponse(BaseModel):
    """Deal representation returned by the API.

    Attributes:
        id: Deal UUID.
        title: Product title.
        url: Deal URL.
        sale_price: Current sale price.
        original_price: Original retail price (if available).
        estimated_value: Bedrock-estimated fair market value.
        discount_percentage: Calculated discount percentage.
        is_high_value: Whether the deal meets the discount threshold.
        category: Product category.
        brand: Brand name.
        status: Deal processing status.
        source_name: Name of the RSS feed source.
    """

    id: UUID
    title: str
    url: str
    sale_price: Optional[Decimal] = None
    original_price: Optional[Decimal] = None
    estimated_value: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    is_high_value: bool
    category: Optional[str] = None
    brand: Optional[str] = None
    status: str
    source_name: Optional[str] = None

    model_config = {"from_attributes": True}


class DealListResponse(BaseModel):
    """Paginated list of deals.

    Attributes:
        items: List of deal summaries.
        total: Total number of matching deals.
        limit: Page size used.
        offset: Offset used.
    """

    items: list[DealResponse]
    total: int
    limit: int
    offset: int


# ─────────────────────────────────────────────
# User schemas
# ─────────────────────────────────────────────


class UserCreate(BaseModel):
    """Request body for user creation.

    Attributes:
        email: User email address (must be unique).
        username: Chosen username (must be unique).
        password: Plain-text password (hashed before storage).
        full_name: Optional display name.
    """

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class SavedFeed(BaseModel):
    """A single saved feed filter entry.

    Attributes:
        category: Category or subcategory value to filter by.
        status: Deal status filter (empty string means all statuses).
    """

    category: str
    status: str = ""


class UserPreferencesUpdate(BaseModel):
    """Request body for updating notification preferences.

    Attributes:
        notification_preferences: Channel-level opt-in/opt-out flags.
        discount_threshold: Minimum discount to trigger a notification.
        preferred_categories: Categories the user is interested in.
        saved_feeds: User's saved feed filters for the Feed page UI.
    """

    notification_preferences: Optional[dict] = None
    discount_threshold: Optional[Decimal] = Field(None, ge=0, le=100)
    preferred_categories: Optional[list[str]] = None
    saved_feeds: Optional[list[SavedFeed]] = None


class UserResponse(BaseModel):
    """User representation returned by the API.

    Attributes:
        id: User UUID.
        email: Email address.
        username: Username.
        full_name: Display name.
        is_active: Whether the account is active.
        discount_threshold: User's personal notification threshold.
        preferred_categories: List of preferred categories.
        notification_preferences: JSONB preferences dict (includes saved_feeds).
    """

    id: UUID
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    discount_threshold: Decimal
    preferred_categories: Optional[list] = None
    notification_preferences: Optional[dict] = None
    # pushover_user_key removed — notifications now via SNS topic subscription

    model_config = {"from_attributes": True}


class PreferencesUpdateResponse(UserResponse):
    """Response for PUT /users/{id}/preferences.

    Extends UserResponse with an optional informational message shown
    when saved feeds are modified (e.g. to set latency expectations).

    Attributes:
        message: Optional human-readable note for the caller.
    """

    message: Optional[str] = None
