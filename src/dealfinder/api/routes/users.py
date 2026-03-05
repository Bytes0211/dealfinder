"""User endpoints for the Deal Finder REST API.

Endpoints:
    POST /users              — create a new user account
    GET  /users/{id}         — get user profile (authenticated, own record only)
    PUT  /users/{id}/preferences — update notification preferences
"""

import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import bcrypt

from dealfinder.api.deps import get_current_user_id, get_db, get_token_claims
from dealfinder.api.schemas import UserCreate, UserPreferencesUpdate, UserResponse, SavedFeed  # noqa: F401
from dealfinder.data.repository import UserRepository
from dealfinder.db.models import User

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
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cannot provision account: no email claim in token",
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
        user = await repo.create(new_user)
        logger.info(f"Auto-provisioned Cognito user {user_id} ({email})")
    except IntegrityError:
        # Concurrent request already created the record — just fetch it.
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


@router.put("/{user_id}/preferences", response_model=UserResponse,
            summary="Update notification preferences")
async def update_preferences(
    user_id: UUID,
    body: UserPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
    token_claims: dict = Depends(get_token_claims),
) -> UserResponse:
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

    if body.discount_threshold is not None:
        user.discount_threshold = body.discount_threshold
    if body.preferred_categories is not None:
        user.preferred_categories = body.preferred_categories
    if body.pushover_user_key is not None:
        user.pushover_user_key = body.pushover_user_key

    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)
