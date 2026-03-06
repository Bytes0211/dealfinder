"""Pydantic request/response schemas for the Deal Finder API.

All schemas use snake_case field names matching the ORM models.
UUID fields are serialised as strings for JSON compatibility.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


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
    is_high_value: True if the deal meets the discount threshold.
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
    """A saved watchlist feed item from a Tavily search.

    Attributes:
        id: Unique identifier for this feed entry.
        query: Original search query used to find this item.
        title: Product title extracted by Bedrock.
        url: Product URL.
        current_price: Current price string at time of search (e.g. "$279.99").
        min_discount: Minimum discount percentage to trigger a notification.
        quality_score: Bedrock deal quality score 0–10.
        quality_reason: Brief explanation of the quality score.
        saved_at: ISO timestamp when the feed was saved.
    """

    id: str
    query: str
    title: str
    url: str
    current_price: Optional[str] = None
    min_discount: int = 0
    quality_score: Optional[float] = None
    quality_reason: Optional[str] = None
    saved_at: str


class UserPreferencesUpdate(BaseModel):
    """Request body for updating notification preferences.

    Attributes:
        notification_preferences: Channel-level opt-in/opt-out flags.
        saved_feeds: User's saved watchlist feed items.
        phone_number: E.164-formatted phone number for SNS SMS notifications.
    """

    notification_preferences: Optional[dict] = None
    saved_feeds: Optional[list[SavedFeed]] = None
    phone_number: Optional[str] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Validate E.164 phone number format.

        Args:
            v: Phone number string or None.

        Returns:
            Validated phone number string.

        Raises:
            ValueError: If the phone number does not match E.164 format.
        """
        import re
        if v is not None and not re.match(r"^\+[1-9]\d{1,14}$", v):
            raise ValueError("Phone number must be in E.164 format (e.g. +12125551234)")
        return v


class UserResponse(BaseModel):
    """User representation returned by the API.

    Attributes:
        id: User UUID.
        email: Email address.
        username: Username.
        full_name: Display name.
        is_active: Whether the account is active.
        phone_number: E.164 phone number for SNS SMS notifications.
        notification_preferences: JSONB preferences dict (includes saved_feeds).
    """

    id: UUID
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    phone_number: Optional[str] = None
    notification_preferences: Optional[dict] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Search schemas
# ─────────────────────────────────────────────


class SearchRequest(BaseModel):
    """Request body for the Tavily + Bedrock deal search.

    Attributes:
        query: Free-text product search query.
        max_results: Maximum number of results to return (1–20).
    """

    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(10, ge=1, le=20)


class SearchResult(BaseModel):
    """A single search result enriched by Bedrock.

    Attributes:
        title: Cleaned product title.
        url: Product URL.
        current_price: Current price string (e.g. "$279.99") or None.
        quality_score: Bedrock deal quality score 0–10.
        quality_reason: Brief explanation of the quality score (max 15 words).
    """

    title: str
    url: str
    current_price: Optional[str] = None
    quality_score: Optional[float] = None
    quality_reason: Optional[str] = None


class SearchResponse(BaseModel):
    """Response from the deal search endpoint.

    Attributes:
        query: The original search query.
        results: List of enriched search results.
    """

    query: str
    results: list[SearchResult]


# ─────────────────────────────────────────────
# Preferences update response
# ─────────────────────────────────────────────


class PreferencesUpdateResponse(UserResponse):
    """Response for PUT /users/{id}/preferences.

    Extends UserResponse with an optional informational message shown
    when saved feeds are modified (e.g. to set latency expectations).

    Attributes:
        message: Optional human-readable note for the caller.
    """

    message: Optional[str] = None
