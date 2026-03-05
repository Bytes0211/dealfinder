"""Unit tests for GET /api/v1/health."""

from dealfinder.api.main import app
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_ok(self) -> None:
        """GET /api/v1/health should return 200 with status ok."""
        with TestClient(app) as client:
            response = client.get("/api/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "dealfinder-api"
