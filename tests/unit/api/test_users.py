"""Unit tests for user API endpoints.

POST /users                      — create account
PUT  /users/{id}/preferences     — update preferences (auth required)
DELETE /users/{id}               — deactivate account (auth required)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError


class TestCreateUser:
    """Tests for POST /api/v1/users."""

    def test_creates_user_and_returns_201(self, client) -> None:
        """Valid request body should create a user and return 201."""
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "password123",
            "full_name": "New User",
        }
        response = client.post("/api/v1/users", json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "newuser@example.com"
        assert body["username"] == "newuser"
        assert body["is_active"] is True
        # Password must not be leaked
        assert "password" not in body
        assert "hashed_password" not in body

    def test_returns_409_for_duplicate_email(self, client, user) -> None:
        """A second registration with the same email should return 409."""
        payload = {
            "email": user.email,
            "username": "otheruser",
            "password": "password123",
        }
        response = client.post("/api/v1/users", json=payload)
        assert response.status_code == 409

    def test_returns_409_for_duplicate_username(self, client, user) -> None:
        """A second registration with the same username should return 409."""
        payload = {
            "email": "other@example.com",
            "username": user.username,
            "password": "password123",
        }
        response = client.post("/api/v1/users", json=payload)
        assert response.status_code == 409

    def test_returns_422_for_invalid_email(self, client) -> None:
        """An invalid email format should return 422."""
        response = client.post("/api/v1/users", json={
            "email": "not-an-email",
            "username": "u",
            "password": "password123",
        })
        assert response.status_code == 422

    def test_returns_422_for_short_password(self, client) -> None:
        """A password shorter than 8 characters should return 422."""
        response = client.post("/api/v1/users", json={
            "email": "x@example.com",
            "username": "validname",
            "password": "short",
        })
        assert response.status_code == 422

    def test_returns_409_on_integrity_error(self, client) -> None:
        """A race condition causing IntegrityError on repo.create should return 409."""
        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=None)
        mock_repo.get_by_username = AsyncMock(return_value=None)
        mock_repo.create = AsyncMock(
            side_effect=IntegrityError("INSERT", {}, Exception("unique constraint"))
        )

        with patch("dealfinder.api.routes.users.UserRepository", return_value=mock_repo):
            response = client.post("/api/v1/users", json={
                "email": "race@example.com",
                "username": "raceuser",
                "password": "password123",
            })
        assert response.status_code == 409


class TestUpdateUserPreferences:
    """Tests for PUT /api/v1/users/{user_id}/preferences."""

    def test_updates_preferences_with_valid_auth(self, client, user) -> None:
        """Owner should be able to update their own preferences."""
        payload = {
            "notification_preferences": {"email": True},
            "discount_threshold": "30.00",
        }
        response = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json=payload,
            headers={"X-Test-User-Id": str(user.id)},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(user.id)

    def test_returns_403_for_different_user(self, client, user) -> None:
        """Attempting to update another user's preferences should return 403."""
        different_user_id = str(uuid4())
        payload = {"notification_preferences": {}}
        response = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json=payload,
            headers={"X-Test-User-Id": different_user_id},
        )
        assert response.status_code == 403

    def test_returns_401_without_auth_header(self, client, user) -> None:
        """Missing authentication should return 401."""
        payload = {"notification_preferences": {}}
        response = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json=payload,
            # No X-Test-User-Id header
        )
        assert response.status_code == 401

    def test_returns_404_for_unknown_user(self, client) -> None:
        """An unknown user_id should return 404 (after auth passes)."""
        unknown_id = str(uuid4())
        payload = {"notification_preferences": {}}
        response = client.put(
            f"/api/v1/users/{unknown_id}/preferences",
            json=payload,
            headers={"X-Test-User-Id": unknown_id},
        )
        assert response.status_code == 404

    def test_updates_phone_number(self, client, user) -> None:
        """A valid E.164 phone number should be accepted and returned."""
        response = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json={"phone_number": "+12125551234"},
            headers={"X-Test-User-Id": str(user.id)},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["phone_number"] == "+12125551234"

    def test_rejects_invalid_phone_number(self, client, user) -> None:
        """A phone number that is not E.164 should return 422."""
        response = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json={"phone_number": "not-a-phone"},
            headers={"X-Test-User-Id": str(user.id)},
        )
        assert response.status_code == 422

    def test_saves_feeds_to_watchlist(self, client, user) -> None:
        """Saving saved_feeds should persist them in notification_preferences."""
        payload = {
            "saved_feeds": [
                {
                    "id": "feed-001",
                    "query": "sony headphones",
                    "title": "Sony WH-1000XM5",
                    "url": "https://example.com/sony",
                    "current_price": "$249.99",
                    "quality_score": 8.5,
                    "quality_reason": "Strong brand, good discount",
                    "saved_at": "2026-03-06T04:00:00Z",
                }
            ]
        }
        response = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json=payload,
            headers={"X-Test-User-Id": str(user.id)},
        )
        assert response.status_code == 200
        body = response.json()
        feeds = body["notification_preferences"]["saved_feeds"]
        assert len(feeds) == 1
        assert feeds[0]["title"] == "Sony WH-1000XM5"



class TestGetOrProvisionUser:
    """Unit tests for the _get_or_provision_user helper.

    Tests auto-provisioning logic in isolation, including the SAVEPOINT-based
    race-condition fix that prevents HTTP 500 when two concurrent requests
    attempt to create the same Cognito user simultaneously.
    """

    async def test_returns_existing_user_from_db(self) -> None:
        """If the user already exists, return it without calling create."""
        from dealfinder.api.routes.users import _get_or_provision_user

        user_id = uuid4()
        existing = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=existing)

        result = await _get_or_provision_user(user_id, {}, mock_repo)

        assert result is existing
        mock_repo.create.assert_not_called()

    async def test_provisions_new_user_from_token_claims(self) -> None:
        """If no DB record exists, auto-provision a new user from the token email."""
        from dealfinder.api.routes.users import _get_or_provision_user

        user_id = uuid4()
        new_user = MagicMock()

        mock_cm = AsyncMock()
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.begin_nested = MagicMock(return_value=mock_cm)

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)
        mock_repo._get_session = AsyncMock(return_value=mock_session)
        mock_repo.create = AsyncMock(return_value=new_user)

        result = await _get_or_provision_user(
            user_id, {"username": "new@example.com"}, mock_repo
        )

        assert result is new_user
        mock_repo.create.assert_called_once()

    async def test_recovers_from_concurrent_insert_via_savepoint(self) -> None:
        """IntegrityError from a concurrent INSERT is handled without leaving the
        session in a failed transaction state.

        Pre-fix behaviour: repo.get_by_id() after IntegrityError would raise
        InFailedSQLTransactionError because the transaction was aborted.
        Post-fix behaviour: begin_nested() rolls back only the SAVEPOINT;
        the outer transaction remains valid so the retry get_by_id succeeds.
        """
        from dealfinder.api.routes.users import _get_or_provision_user

        user_id = uuid4()
        existing = MagicMock()

        # __aexit__ returns False so IntegrityError is not suppressed and
        # propagates to our except IntegrityError block.
        mock_cm = AsyncMock()
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.begin_nested = MagicMock(return_value=mock_cm)

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(side_effect=[None, existing])
        mock_repo._get_session = AsyncMock(return_value=mock_session)
        mock_repo.create = AsyncMock(
            side_effect=IntegrityError("INSERT", {}, Exception("unique_violation"))
        )

        result = await _get_or_provision_user(
            user_id, {"username": "race@example.com"}, mock_repo
        )

        assert result is existing
        assert mock_repo.get_by_id.call_count == 2

    async def test_raises_404_when_token_has_no_identity(self) -> None:
        """Token with no email/username/cognito:username claim raises HTTP 404."""
        from dealfinder.api.routes.users import _get_or_provision_user

        user_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await _get_or_provision_user(user_id, {}, mock_repo)
        assert exc_info.value.status_code == 404


# ─────────────────────────────────────────────
# Watchlist-deal-cleanup fixtures
# ─────────────────────────────────────────────


@pytest.fixture
async def watchlist_source_and_deal(session, user):
    """Seed a watchlist DealSource + Deal, and pre-set the user's saved_feeds."""
    from decimal import Decimal
    from dealfinder.db.models import Deal, DealSource, DealStatus

    user.notification_preferences = {
        "saved_feeds": [
            {
                "id": "f-1",
                "query": "sony headphones",
                "title": "Sony WH-1000XM5",
                "url": "https://example.com/sony",
                "saved_at": "2026-03-20T00:00:00Z",
            }
        ]
    }
    src = DealSource(
        name="sony headphones",
        url="watchlist://sony headphones",
        is_active=True,
    )
    session.add(src)
    await session.flush()
    await session.refresh(src)
    deal = Deal(
        source_id=src.id,
        external_id="wl-001",
        title="Sony WH-1000XM5",
        url="https://example.com/sony",
        is_high_value=True,
        status=DealStatus.EVALUATED,
    )
    session.add(deal)
    await session.commit()
    await session.refresh(src)
    await session.refresh(deal)
    return {"source": src, "deal": deal}


@pytest.fixture
async def watchlist_shared_by_other_user(session, user):
    """Seed a shared watchlist query: two users watch 'sony headphones'."""
    import bcrypt
    from decimal import Decimal
    from dealfinder.db.models import Deal, DealSource, DealStatus, User

    # Current user has the feed
    user.notification_preferences = {
        "saved_feeds": [
            {
                "id": "f-1",
                "query": "sony headphones",
                "title": "Sony WH-1000XM5",
                "url": "https://example.com/sony",
                "saved_at": "2026-03-20T00:00:00Z",
            }
        ]
    }
    # Another active user watches the same query
    other = User(
        email="other@example.com",
        username="otheruser",
        hashed_password=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
        is_active=True,
        notification_preferences={
            "saved_feeds": [
                {
                    "id": "f-other",
                    "query": "sony headphones",
                    "title": "Sony",
                    "url": "https://example.com/sony",
                    "saved_at": "2026-03-20T00:00:00Z",
                }
            ]
        },
    )
    session.add(other)
    src = DealSource(
        name="sony headphones",
        url="watchlist://sony headphones",
        is_active=True,
    )
    session.add(src)
    await session.flush()
    await session.refresh(src)
    deal = Deal(
        source_id=src.id,
        external_id="wl-002",
        title="Sony WH-1000XM5",
        url="https://example.com/sony2",
        is_high_value=True,
        status=DealStatus.EVALUATED,
    )
    session.add(deal)
    await session.commit()
    await session.refresh(src)
    await session.refresh(deal)
    return {"source": src, "deal": deal, "other_user": other}


class TestWatchlistDealCleanup:
    """Tests for orphaned watchlist deal cleanup on feed removal."""

    def test_removes_orphaned_deals_on_feed_removal(
        self, client, user, watchlist_source_and_deal,
    ) -> None:
        """Removing a feed should delete its watchlist:// deals when no other user watches it."""
        resp = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json={"saved_feeds": []},
            headers={"X-Test-User-Id": str(user.id)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "orphaned deal(s) removed" in body["message"]

    def test_preserves_deals_when_another_user_watches_same_query(
        self, client, user, watchlist_shared_by_other_user,
    ) -> None:
        """Deals should NOT be deleted when another active user has the same query."""
        resp = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json={"saved_feeds": []},
            headers={"X-Test-User-Id": str(user.id)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == (
            "Feed saved. New deals matching your watchlist will trigger notifications."
        )

class TestDeleteUser:
    """Tests for DELETE /api/v1/users/{user_id}."""

    def test_deactivates_own_account(self, client, user) -> None:
        """Owner should be able to deactivate their own account."""
        response = client.delete(
            f"/api/v1/users/{user.id}",
            headers={"X-Test-User-Id": str(user.id)},
        )
        assert response.status_code == 204

    def test_returns_403_for_different_user(self, client, user) -> None:
        """Attempting to deactivate another user's account should return 403."""
        different_user_id = str(uuid4())
        response = client.delete(
            f"/api/v1/users/{user.id}",
            headers={"X-Test-User-Id": different_user_id},
        )
        assert response.status_code == 403

    def test_returns_401_without_auth(self, client, user) -> None:
        """Missing auth header should return 401."""
        response = client.delete(f"/api/v1/users/{user.id}")
        assert response.status_code == 401

    def test_returns_404_for_unknown_user(self, client) -> None:
        """An unknown user_id should return 404 (after auth passes)."""
        unknown_id = str(uuid4())
        response = client.delete(
            f"/api/v1/users/{unknown_id}",
            headers={"X-Test-User-Id": unknown_id},
        )
        assert response.status_code == 404
