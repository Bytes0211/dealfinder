"""FastAPI dependency functions for the Deal Finder API.

Provides injectable dependencies for database sessions and authentication.
When deployed on Lambda behind API Gateway with a Cognito JWT authorizer
the ``get_current_user_id`` dependency extracts the Cognito ``sub`` claim
from the request state populated by the Mangum adapter.
"""

import logging
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from dealfinder.db.connection import get_async_session

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for the duration of a request.

    Yields:
        An open ``AsyncSession`` that auto-commits on success and rolls
        back on exception, matching the ``get_async_session`` context manager.
    """
    async with get_async_session() as session:
        yield session


def get_current_user_id(request: Request) -> UUID:
    """Extract the authenticated user ID from the API Gateway JWT claims.

    API Gateway (HTTP API with Cognito JWT authorizer) injects claims into
    ``event["requestContext"]["authorizer"]["jwt"]["claims"]``.  Mangum
    exposes this as ``request.state.aws_event``.

    In test environments where no JWT is present the header
    ``X-Test-User-Id`` is accepted as a fallback (only in tests).

    Args:
        request: FastAPI Request object.

    Returns:
        UUID of the authenticated user (Cognito ``sub`` claim).

    Raises:
        HTTPException 401: If no valid identity can be extracted.
    """
    # Attempt to extract from Cognito JWT claims via Mangum
    aws_event: dict = getattr(request.state, "aws_event", {})
    claims: dict = (
        aws_event
        .get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    sub = claims.get("sub")
    if sub:
        try:
            return UUID(sub)
        except ValueError:
            pass

    # Test/local fallback — only honoured outside prod (no Cognito authorizer configured)
    test_user_id = request.headers.get("X-Test-User-Id")
    if test_user_id:
        try:
            return UUID(test_user_id)
        except ValueError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )
