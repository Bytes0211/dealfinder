"""User endpoints for the Deal Finder REST API.

Endpoints:
    POST   /users                          — create a new user account
    GET    /users/{id}                     — get user profile (authenticated, own record only)
    PUT    /users/{id}/preferences         — update notification preferences
    DELETE /users/{id}                     — deactivate account
    GET    /users/{id}/watchlist/matches   — paginated deals matching saved feeds
"""

import asyncio
import logging
import os
from uuid import UUID

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import bcrypt

from dealfinder.api.deps import get_current_user_id, get_db, get_token_claims
from dealfinder.api.schemas import (  # noqa: F401
    DealListResponse,
    DealResponse,
    PreferencesUpdateResponse,
    SavedFeed,
    UserCreate,
    UserPreferencesUpdate,
    UserResponse,
)
from dealfinder.data.repository import UserRepository
from dealfinder.db.models import Deal, DealStatus, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


async def _get_or_provision_user(
    user_id: UUID,
    token_claims: dict,
    repo: UserRepository,
) -> User:
    """Return an existing User or auto-provision one for a new Cognito user.

    Cognito-authenticated users have a ``sub`` UUID that has no corresponding
    DB record until they first interact with a user-scoped endpoint.  We create
    a minimal record on-demand, using the Cognito sub as the PK and the token
    ``username`` claim (= email, since ``username_attributes = [email]``) for
    required fields.  The hashed_password is randomised — login is always via
    Cognito so this field is never used.

    Args:
        user_id: Cognito sub UUID (becomes the DB primary key).
        token_claims: Decoded JWT payload from the Bearer token.
        repo: UserRepository bound to the current session.

    Returns:
        Existing or newly created User instance.

    Raises:
        HTTPException 401: If the token carries no usable identity (no username claim).
    """
    user = await repo.get_by_id(user_id)
    if user:
        return user

    # Cognito access tokens set `username` to the sign-in email when
    # username_attributes = ["email"]
    email: str | None = (
        token_claims.get("username")
        or token_claims.get("email")
        or token_claims.get("cognito:username")
    )
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    random_pw = os.urandom(32).hex()
    hashed = bcrypt.hashpw(random_pw.encode(), bcrypt.gensalt()).decode()
    new_user = User(
        id=user_id,
        email=email,
        username=str(user_id),   # sub UUID — always unique
        hashed_password=hashed,
    )
    try:
        # Use a SAVEPOINT so that an IntegrityError from a concurrent insert
        # only rolls back the nested transaction, leaving the outer session
        # healthy for the subsequent get_by_id retry.  Without begin_nested()
        # the session would be left in an aborted-transaction state after the
        # IntegrityError, causing the retry query to raise
        # InFailedSQLTransactionError and bubble up as an unhandled HTTP 500.
        session = await repo._get_session()
        async with session.begin_nested():
            user = await repo.create(new_user)
        logger.info(f"Auto-provisioned Cognito user {user_id} ({email})")
    except IntegrityError:
        # A concurrent request already created the record.  The SAVEPOINT was
        # rolled back above so the outer transaction is still valid — fetch the
        # existing row.
        user = await repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to provision user account",
            )
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED,
             summary="Create user account")
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user account.

    Args:
        body: User creation request.
        db: Injected database session.

    Returns:
        Created user response.

    Raises:
        HTTPException 409: If the email or username is already taken.
    """
    repo = UserRepository(db)

    if await repo.get_by_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address already registered",
        )
    if await repo.get_by_username(body.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hashed,
        full_name=body.full_name,
    )
    try:
        user = await repo.create(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address or username already registered",
        )
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse, summary="Get user profile")
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
    token_claims: dict = Depends(get_token_claims),
) -> UserResponse:
    """Return a user's profile and preferences.

    Users may only fetch their own profile.  If no DB record exists yet for the
    Cognito user, one is auto-provisioned from the token claims.

    Args:
        user_id: UUID of the user to retrieve.
        db: Injected database session.
        current_user_id: UUID of the authenticated caller.
        token_claims: Decoded JWT claims (used for auto-provisioning).

    Returns:
        User profile response.

    Raises:
        HTTPException 403: If the caller is not the account owner.
    """
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's profile",
        )
    repo = UserRepository(db)
    user = await _get_or_provision_user(user_id, token_claims, repo)
    return UserResponse.model_validate(user)


@router.put("/{user_id}/preferences", response_model=PreferencesUpdateResponse,
            summary="Update notification preferences")
async def update_preferences(
    user_id: UUID,
    body: UserPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
    token_claims: dict = Depends(get_token_claims),
) -> PreferencesUpdateResponse:
    """Update a user's notification preferences.

    Users may only update their own preferences.  If no DB record exists yet
    for the Cognito user it is auto-provisioned from the token claims.

    Args:
        user_id: UUID of the user to update.
        body: Preference fields to apply.
        db: Injected database session.
        current_user_id: UUID of the authenticated caller.
        token_claims: Decoded JWT claims (used for auto-provisioning).

    Returns:
        Updated user response.

    Raises:
        HTTPException 403: If the caller is not the account owner.
    """
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update another user's preferences",
        )

    repo = UserRepository(db)
    user = await _get_or_provision_user(user_id, token_claims, repo)

    # Merge notification_preferences dict rather than replacing it wholesale
    prefs: dict = dict(user.notification_preferences or {})
    if body.notification_preferences is not None:
        prefs.update(body.notification_preferences)
    if body.saved_feeds is not None:
        prefs["saved_feeds"] = [f.model_dump() for f in body.saved_feeds]
    user.notification_preferences = prefs

    # Phone number update: validate + SNS SMS subscribe
    if body.phone_number is not None:
        user.phone_number = body.phone_number
        _subscribe_phone_to_sns(body.phone_number)

    await db.flush()
    await db.refresh(user)

    message: str | None = None
    if body.saved_feeds is not None:
        message = "Feed saved. New deals matching your watchlist will trigger notifications."

    return PreferencesUpdateResponse(
        **UserResponse.model_validate(user).model_dump(),
        message=message,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate account")
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
    token_claims: dict = Depends(get_token_claims),
) -> None:
    """Deactivate a user account (soft delete).

    Sets is_active = False. The account record is retained for audit purposes.
    Users may only deactivate their own account.

    Args:
        user_id: UUID of the user to deactivate.
        db: Injected database session.
        current_user_id: UUID of the authenticated caller.
        token_claims: Decoded JWT claims.

    Raises:
        HTTPException 403: If the caller is not the account owner.
        HTTPException 404: If the user does not exist.
    """
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deactivate another user's account",
        )
    repo = UserRepository(db)
    user = await _get_or_provision_user(user_id, token_claims, repo)
    user.is_active = False
    await db.flush()
    logger.info(f"Account deactivated: {user_id} ({user.email})")


@router.get(
    "/{user_id}/watchlist/matches",
    response_model=DealListResponse,
    summary="Deals matching the user's saved watchlist feeds",
)
async def watchlist_matches(
    user_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
    token_claims: dict = Depends(get_token_claims),
) -> DealListResponse:
    """Return paginated deals from the RSS pipeline that match saved watchlist items.

    For each saved feed entry, keywords from the feed's ``query`` field are
    matched against deal titles using case-insensitive substring search.
    Results are filtered by the feed's ``min_discount`` threshold, deduplicated,
    and sorted by discovery date descending.

    Args:
        user_id: UUID of the user whose watchlist to match against.
        limit: Page size (max 100).
        offset: Pagination offset.
        db: Injected database session.
        current_user_id: UUID of the authenticated caller.
        token_claims: Decoded JWT claims.

    Returns:
        Paginated DealListResponse with total count.

    Raises:
        HTTPException 403: If the caller is not the account owner.
    """
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view another user's watchlist matches",
        )

    repo = UserRepository(db)
    user = await _get_or_provision_user(user_id, token_claims, repo)

    saved_feeds: list[dict] = (
        (user.notification_preferences or {}).get("saved_feeds", []) or []
    )

    if not saved_feeds:
        return DealListResponse(items=[], total=0, limit=limit, offset=offset)

    # Build OR filter: one ILIKE condition per feed query keyword
    ilike_conditions = []
    min_discounts: list[float] = []
    for feed in saved_feeds:
        query_str = feed.get("query", "").strip()
        if query_str:
            # Split query into up to 3 significant keywords for broad matching
            keywords = [w for w in query_str.split() if len(w) > 2][:3]
            for kw in keywords:
                ilike_conditions.append(Deal.title.ilike(f"%{kw}%"))
            min_discounts.append(float(feed.get("min_discount", 0)))

    if not ilike_conditions:
        return DealListResponse(items=[], total=0, limit=limit, offset=offset)

    min_discount_overall = min(min_discounts) if min_discounts else 0

    base_query = (
        select(Deal)
        .options(selectinload(Deal.source))
        .where(
            or_(*ilike_conditions),
            Deal.discount_percentage >= min_discount_overall,
        )
    )
    count_query = (
        select(func.count())
        .select_from(Deal)
        .where(
            or_(*ilike_conditions),
            Deal.discount_percentage >= min_discount_overall,
        )
    )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(
        base_query.order_by(desc(Deal.discovered_at)).offset(offset).limit(limit)
    )
    deals = result.scalars().all()

    items = [
        DealResponse(
            id=deal.id,
            title=deal.title,
            url=deal.url,
            sale_price=deal.sale_price,
            original_price=deal.original_price,
            estimated_value=deal.estimated_value,
            discount_percentage=deal.discount_percentage,
            is_high_value=deal.is_high_value,
            category=deal.category,
            brand=deal.brand,
            status=deal.status.value,
            source_name=deal.source.name if deal.source else None,
        )
        for deal in deals
    ]
    return DealListResponse(items=items, total=total, limit=limit, offset=offset)


def _subscribe_phone_to_sns(phone_number: str) -> None:
    """Subscribe a phone number to the SNS deal notifications topic.

    Best-effort: logs errors but does not raise so that a failed SNS
    subscription does not block preference updates.

    Args:
        phone_number: E.164-formatted phone number (e.g. +12125551234).
    """
    topic_arn = os.getenv("DEALFINDER_SNS_TOPIC_ARN", "")
    region = os.getenv("AWS_REGION", "us-east-1")
    if not topic_arn:
        logger.warning("SNS topic ARN not configured — skipping SMS subscription")
        return
    try:
        sns = boto3.client("sns", region_name=region)
        response = sns.subscribe(
            TopicArn=topic_arn,
            Protocol="sms",
            Endpoint=phone_number,
        )
        logger.info(f"SNS SMS subscription created for {phone_number}: {response.get('SubscriptionArn')}")
    except ClientError as e:
        logger.error(f"SNS subscribe failed for {phone_number}: {e}")
