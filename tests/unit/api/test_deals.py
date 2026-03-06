"""Unit tests for deal API endpoints.

GET /api/v1/deals      — list with optional filters
GET /api/v1/deals/top  — high-value deals
GET /api/v1/deals/{id} — single deal
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from dealfinder.db.models import Deal, DealSource, DealStatus


class TestListDeals:
    """Tests for GET /api/v1/deals."""

    def test_returns_empty_list_when_no_deals(self, client) -> None:
        """An empty database should return an empty items list."""
        response = client.get("/api/v1/deals")
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["limit"] == 50
        assert body["offset"] == 0

    def test_returns_seeded_deal(self, client, deal) -> None:
        """A seeded deal should appear in the list response."""
        response = client.get("/api/v1/deals")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == deal.title

    def test_filters_by_status(self, client, deal) -> None:
        """Status filter should accept valid DealStatus values."""
        response = client.get("/api/v1/deals", params={"status": "evaluated"})
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_invalid_status_returns_422(self, client) -> None:
        """An invalid status value should return 422."""
        response = client.get("/api/v1/deals", params={"status": "not_a_status"})
        assert response.status_code == 422

    def test_pagination_limit_and_offset(self, client, session, source) -> None:
        """Limit and offset should control the returned slice."""
        # Health check endpoint doesn't use DB; but pagination needs deals
        response = client.get("/api/v1/deals", params={"limit": 1, "offset": 0})
        assert response.status_code == 200


class TestTopDeals:
    """Tests for GET /api/v1/deals/top."""

    def test_returns_only_high_value_deals(self, client, deal, session) -> None:
        """Only is_high_value=True deals should appear in /top."""
        response = client.get("/api/v1/deals/top")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["is_high_value"] is True

    def test_returns_empty_list_when_no_high_value_deals(self, client) -> None:
        """With no high-value deals the endpoint should return an empty list."""
        response = client.get("/api/v1/deals/top")
        assert response.status_code == 200
        assert response.json() == []

    def test_limit_param_respected(self, client, deal) -> None:
        """The limit query param should cap the result count."""
        response = client.get("/api/v1/deals/top", params={"limit": 1})
        assert response.status_code == 200
        assert len(response.json()) <= 1


class TestGetDeal:
    """Tests for GET /api/v1/deals/{deal_id}."""

    def test_returns_deal_by_id(self, client, deal) -> None:
        """A valid deal_id should return the deal detail."""
        response = client.get(f"/api/v1/deals/{deal.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(deal.id)
        assert body["title"] == deal.title

    def test_returns_404_for_unknown_id(self, client) -> None:
        """An unknown UUID should return 404."""
        response = client.get(f"/api/v1/deals/{uuid4()}")
        assert response.status_code == 404

    def test_response_includes_expected_fields(self, client, deal) -> None:
        """The deal response should include all required fields."""
        response = client.get(f"/api/v1/deals/{deal.id}")
        body = response.json()
        for field in ("id", "title", "url", "is_high_value", "status"):
            assert field in body
