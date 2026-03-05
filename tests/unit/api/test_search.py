"""Unit tests for the search API endpoint.

POST /api/v1/search — Tavily web search + Bedrock extraction
"""

from unittest.mock import AsyncMock, MagicMock, patch

# Patch target: the async helper and Bedrock class inside the route module
_CALL_TAVILY = "dealfinder.api.routes.search._call_tavily"
_EXTRACTOR = "dealfinder.api.routes.search.BedrockSearchExtractor"
_CONFIG = "dealfinder.api.routes.search.AgentConfig"


def _mock_config(api_key: str = "test-tavily-key") -> MagicMock:
    """Return a mock AgentConfig with a non-empty tavily_api_key."""
    cfg = MagicMock()
    cfg.tavily_api_key = api_key
    return cfg


class TestSearch:
    """Tests for POST /api/v1/search."""

    def test_returns_search_results(self, client) -> None:
        """Valid query should return a list of results with quality scoring."""
        mock_results = [
            {
                "title": "Sony WH-1000XM5 Headphones – $249",
                "url": "https://example.com/sony",
                "current_price": "$249",
                "quality_score": 8,
                "quality_reason": "Well below typical retail price.",
            },
        ]

        with patch(_CONFIG, return_value=_mock_config()), \
             patch(_CALL_TAVILY, new=AsyncMock(return_value=[{"url": "https://example.com/sony", "title": "Sony"}])), \
             patch(_EXTRACTOR) as MockExtractor:
            instance = MockExtractor.return_value
            instance.extract = MagicMock(return_value=mock_results)

            response = client.post("/api/v1/search", json={"query": "Sony headphones"})

        assert response.status_code == 200
        body = response.json()
        assert body["query"] == "Sony headphones"
        assert len(body["results"]) == 1
        result = body["results"][0]
        assert result["title"] == "Sony WH-1000XM5 Headphones – $249"
        assert result["quality_score"] == 8

    def test_returns_empty_results_when_no_tavily_hits(self, client) -> None:
        """If Tavily returns nothing, an empty results list should be returned."""
        with patch(_CONFIG, return_value=_mock_config()), \
             patch(_CALL_TAVILY, new=AsyncMock(return_value=[])), \
             patch(_EXTRACTOR) as MockExtractor:
            instance = MockExtractor.return_value
            instance.extract = MagicMock(return_value=[])

            response = client.post("/api/v1/search", json={"query": "xyznothing"})

        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_returns_422_for_empty_query(self, client) -> None:
        """An empty query string should return 422 (validation error)."""
        response = client.post("/api/v1/search", json={"query": ""})
        assert response.status_code == 422

    def test_returns_422_for_missing_query(self, client) -> None:
        """A request body without a query field should return 422."""
        response = client.post("/api/v1/search", json={})
        assert response.status_code == 422

    def test_returns_400_when_api_key_not_configured(self, client) -> None:
        """If Tavily API key is missing, the endpoint should return 400."""
        with patch(_CONFIG, return_value=_mock_config(api_key="")):
            response = client.post("/api/v1/search", json={"query": "test item"})
        assert response.status_code == 400

    def test_graceful_bedrock_fallback(self, client) -> None:
        """If Bedrock extraction raises, the endpoint returns 200 with title/url fallback."""
        tavily_hit = {"url": "https://example.com/deal", "title": "Some Deal", "content": "x"}
        with patch(_CONFIG, return_value=_mock_config()), \
             patch(_CALL_TAVILY, new=AsyncMock(return_value=[tavily_hit])), \
             patch(_EXTRACTOR) as MockExtractor:
            instance = MockExtractor.return_value
            instance.extract = MagicMock(side_effect=Exception("Bedrock unavailable"))

            response = client.post("/api/v1/search", json={"query": "test item"})

        # Fallback: returns 200 with raw title/url
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 1
        assert body["results"][0]["url"] == "https://example.com/deal"
