"""User endpoints for the Deal Finder REST API.

Endpoints:
    POST /users              — create a new user account
    PUT  /users/{id}/preferences — update notification preferences
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import bcrypt

from dealfinder.api.deps import get_current_user_id, get_db
from dealfinder.api.schemas import UserCreate, UserPreferencesUpdate, UserResponse
from dealfinder.data.repository import UserRepository
from dealfinder.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


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
    user = await repo.create(user)
    return UserResponse.model_validate(user)


@router.put("/{user_id}/preferences", response_model=UserResponse,
            summary="Update notification preferences")
async def update_preferences(
    user_id: UUID,
    body: UserPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id),
) -> UserResponse:
    """Update a user's notification preferences.

    Users may only update their own preferences.  Cognito JWT authentication
    (injected by API Gateway) provides the caller identity.

    Args:
        user_id: UUID of the user to update.
        body: Preference fields to apply.
        db: Injected database session.
        current_user_id: UUID of the authenticated caller.

    Returns:
        Updated user response.

    Raises:
        HTTPException 403: If the caller is not the account owner.
        HTTPException 404: If the user does not exist.
    """
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update another user's preferences",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.notification_preferences is not None:
        user.notification_preferences = body.notification_preferences
    if body.discount_threshold is not None:
        user.discount_threshold = body.discount_threshold
    if body.preferred_categories is not None:
        user.preferred_categories = body.preferred_categories
    if body.pushover_user_key is not None:
        user.pushover_user_key = body.pushover_user_key

    await db.flush()
    await db.refresh(user)
    return UserResponse.model_validate(user)
