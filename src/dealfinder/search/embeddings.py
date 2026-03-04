"""Embedding service for vector generation.

This module provides an abstraction for generating text embeddings
that can be used with OpenSearch k-NN search.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class EmbeddingConfig(BaseSettings):
    """Configuration for embedding service."""

    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider: openai, bedrock, or local
    provider: str = "openai"

    # OpenAI settings
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "text-embedding-ada-002"
    openai_base_url: str = "https://api.openai.com/v1"

    # AWS Bedrock settings (for future use)
    bedrock_model_id: str = "amazon.titan-embed-text-v1"
    bedrock_region: str = "us-east-1"

    # Dimension for embeddings
    dimension: int = 1536

    # Request settings
    timeout: int = 30
    max_retries: int = 3


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            Vector embedding.
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of vector embeddings.
        """
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider."""

    def __init__(self, config: EmbeddingConfig):
        """Initialize OpenAI provider.

        Args:
            config: Embedding configuration.
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.openai_base_url,
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                timeout=self.config.timeout,
            )
        return self._client

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        # Clean and truncate texts
        cleaned_texts = [self._clean_text(t) for t in texts]

        response = await self.client.post(
            "/embeddings",
            json={
                "input": cleaned_texts,
                "model": self.config.openai_model,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Sort by index to maintain order
        embeddings = sorted(data["data"], key=lambda x: x["index"])
        return [e["embedding"] for e in embeddings]

    def _clean_text(self, text: str, max_tokens: int = 8000) -> str:
        """Clean and truncate text for embedding.

        Args:
            text: Input text.
            max_tokens: Maximum approximate tokens.

        Returns:
            Cleaned text.
        """
        # Simple truncation (rough approximation: 4 chars per token)
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            text = text[:max_chars]
        return text.strip()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 1536):
        """Initialize mock provider.

        Args:
            dimension: Vector dimension.
        """
        self.dimension = dimension

    async def embed_text(self, text: str) -> list[float]:
        """Generate deterministic mock embedding based on text hash."""
        return self._generate_mock_embedding(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings for batch."""
        return [self._generate_mock_embedding(t) for t in texts]

    def _generate_mock_embedding(self, text: str) -> list[float]:
        """Generate deterministic embedding from text hash."""
        # Use hash to generate deterministic but unique vectors
        hash_bytes = hashlib.sha256(text.encode()).digest()

        # Generate vector from hash bytes
        vector = []
        for i in range(self.dimension):
            byte_idx = i % len(hash_bytes)
            value = (hash_bytes[byte_idx] / 255.0) * 2 - 1  # Range [-1, 1]
            vector.append(value)

        # Normalize
        norm = sum(v * v for v in vector) ** 0.5
        return [v / norm for v in vector]


class EmbeddingService:
    """High-level embedding service.

    Example:
        service = EmbeddingService()
        embedding = await service.embed("laptop deal")
        embeddings = await service.embed_batch(["laptop", "phone", "tablet"])
    """

    def __init__(
        self,
        config: Optional[EmbeddingConfig] = None,
        provider: Optional[EmbeddingProvider] = None,
    ):
        """Initialize embedding service.

        Args:
            config: Embedding configuration.
            provider: Optional custom provider.
        """
        if config is None:
            config = EmbeddingConfig()

        self.config = config

        if provider is not None:
            self._provider = provider
        elif config.provider == "openai":
            self._provider = OpenAIEmbeddingProvider(config)
        elif config.provider == "mock":
            self._provider = MockEmbeddingProvider(config.dimension)
        else:
            raise ValueError(f"Unknown embedding provider: {config.provider}")

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            Vector embedding.
        """
        return await self._provider.embed_text(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts.

        Returns:
            List of embeddings.
        """
        return await self._provider.embed_batch(texts)

    async def embed_deal(self, deal: dict[str, Any]) -> list[float]:
        """Generate embedding for a deal.

        Combines title, description, and category into a single embedding.

        Args:
            deal: Deal data dictionary.

        Returns:
            Vector embedding.
        """
        parts = []

        if deal.get("title"):
            parts.append(deal["title"])
        if deal.get("description"):
            parts.append(deal["description"][:500])  # Truncate long descriptions
        if deal.get("category"):
            parts.append(f"Category: {deal['category']}")
        if deal.get("brand"):
            parts.append(f"Brand: {deal['brand']}")

        text = " | ".join(parts)
        return await self.embed(text)

    async def close(self) -> None:
        """Close the embedding service."""
        if hasattr(self._provider, "close"):
            await self._provider.close()
