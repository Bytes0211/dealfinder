"""Unit tests for user API endpoints.

POST /users                      — create account
PUT  /users/{id}/preferences     — update preferences (auth required)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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

    def test_updates_preferred_categories(self, client, user) -> None:
        """Preferred categories list should be updated when provided."""
        response = client.put(
            f"/api/v1/users/{user.id}/preferences",
            json={"preferred_categories": ["Electronics", "Home & Kitchen"]},
            headers={"X-Test-User-Id": str(user.id)},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["preferred_categories"] == ["Electronics", "Home & Kitchen"]
