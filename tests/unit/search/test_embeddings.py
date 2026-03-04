"""Unit tests for embeddings module."""

import pytest

from dealfinder.search.embeddings import (
    EmbeddingConfig,
    EmbeddingService,
    MockEmbeddingProvider,
)


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = EmbeddingConfig()

        assert config.provider == "openai"
        assert config.openai_model == "text-embedding-ada-002"
        assert config.dimension == 1536
        assert config.timeout == 30

    def test_custom_values(self):
        """Test custom configuration values."""
        config = EmbeddingConfig(
            provider="mock",
            dimension=768,
            timeout=60,
        )

        assert config.provider == "mock"
        assert config.dimension == 768
        assert config.timeout == 60


class TestMockEmbeddingProvider:
    """Tests for MockEmbeddingProvider."""

    @pytest.fixture
    def provider(self):
        """Create mock provider."""
        return MockEmbeddingProvider(dimension=128)

    @pytest.mark.asyncio
    async def test_embed_text_returns_vector(self, provider):
        """Test embed_text returns a vector."""
        vector = await provider.embed_text("test text")

        assert isinstance(vector, list)
        assert len(vector) == 128
        assert all(isinstance(v, float) for v in vector)

    @pytest.mark.asyncio
    async def test_embed_text_is_normalized(self, provider):
        """Test embedding is normalized (unit length)."""
        vector = await provider.embed_text("test text")

        # Check norm is approximately 1
        norm = sum(v * v for v in vector) ** 0.5
        assert abs(norm - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_embed_text_is_deterministic(self, provider):
        """Test same text produces same embedding."""
        text = "hello world"
        vector1 = await provider.embed_text(text)
        vector2 = await provider.embed_text(text)

        assert vector1 == vector2

    @pytest.mark.asyncio
    async def test_different_text_different_embedding(self, provider):
        """Test different texts produce different embeddings."""
        vector1 = await provider.embed_text("hello")
        vector2 = await provider.embed_text("world")

        assert vector1 != vector2

    @pytest.mark.asyncio
    async def test_embed_batch(self, provider):
        """Test batch embedding."""
        texts = ["hello", "world", "test"]
        vectors = await provider.embed_batch(texts)

        assert len(vectors) == 3
        assert all(len(v) == 128 for v in vectors)

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self, provider):
        """Test batch embedding with empty list."""
        vectors = await provider.embed_batch([])
        assert vectors == []


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    @pytest.fixture
    def service(self):
        """Create embedding service with mock provider."""
        config = EmbeddingConfig(provider="mock", dimension=128)
        return EmbeddingService(config)

    @pytest.mark.asyncio
    async def test_embed(self, service):
        """Test single text embedding."""
        vector = await service.embed("test text")

        assert isinstance(vector, list)
        assert len(vector) == 128

    @pytest.mark.asyncio
    async def test_embed_batch(self, service):
        """Test batch embedding."""
        texts = ["one", "two", "three"]
        vectors = await service.embed_batch(texts)

        assert len(vectors) == 3

    @pytest.mark.asyncio
    async def test_embed_deal(self, service):
        """Test deal embedding."""
        deal = {
            "title": "Great Laptop Deal",
            "description": "50% off all laptops",
            "category": "electronics",
            "brand": "TechBrand",
        }

        vector = await service.embed_deal(deal)

        assert isinstance(vector, list)
        assert len(vector) == 128

    @pytest.mark.asyncio
    async def test_embed_deal_minimal(self, service):
        """Test deal embedding with minimal data."""
        deal = {"title": "Simple Deal"}

        vector = await service.embed_deal(deal)

        assert isinstance(vector, list)
        assert len(vector) == 128

    def test_unknown_provider_raises_error(self):
        """Test unknown provider raises ValueError."""
        config = EmbeddingConfig(provider="unknown")

        with pytest.raises(ValueError) as exc_info:
            EmbeddingService(config)

        assert "Unknown embedding provider" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close(self, service):
        """Test service close."""
        # Should not raise
        await service.close()
