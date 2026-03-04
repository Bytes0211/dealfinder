"""OpenSearch client for Deal Finder.

This module provides a configured OpenSearch client with connection
pooling and retry logic for production use.
"""

import logging
from typing import Any, Optional

from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import OpenSearchException
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class OpenSearchConfig(BaseSettings):
    """OpenSearch configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="OPENSEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Connection
    host: str = "localhost"
    port: int = 443
    use_ssl: bool = True
    verify_certs: bool = True
    ssl_show_warn: bool = True

    # Authentication
    username: str = "admin"
    password: SecretStr = SecretStr("")

    # Timeouts
    timeout: int = 30
    max_retries: int = 3
    retry_on_timeout: bool = True

    # Index settings
    default_index: str = "deals"
    vector_dimension: int = 1536  # OpenAI ada-002 dimension

    @property
    def hosts(self) -> list[dict[str, Any]]:
        """Get hosts configuration for OpenSearch client."""
        return [{"host": self.host, "port": self.port}]


class OpenSearchClient:
    """OpenSearch client wrapper with connection management.

    This client provides a simplified interface for OpenSearch operations
    with automatic retry and connection pooling.

    Example:
        config = OpenSearchConfig()
        client = OpenSearchClient(config)

        # Search for deals
        results = client.search(
            index="deals",
            body={"query": {"match": {"title": "laptop"}}}
        )

        # Vector search
        results = client.knn_search(
            index="deals",
            vector=[0.1, 0.2, ...],
            k=10
        )
    """

    def __init__(self, config: Optional[OpenSearchConfig] = None):
        """Initialize OpenSearch client.

        Args:
            config: OpenSearch configuration. Uses environment if not provided.
        """
        if config is None:
            config = OpenSearchConfig()

        self.config = config
        self._client: Optional[OpenSearch] = None

    @property
    def client(self) -> OpenSearch:
        """Get or create the OpenSearch client instance."""
        if self._client is None:
            self._client = OpenSearch(
                hosts=self.config.hosts,
                http_auth=(
                    self.config.username,
                    self.config.password.get_secret_value(),
                ),
                use_ssl=self.config.use_ssl,
                verify_certs=self.config.verify_certs,
                ssl_show_warn=self.config.ssl_show_warn,
                connection_class=RequestsHttpConnection,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
                retry_on_timeout=self.config.retry_on_timeout,
            )
        return self._client

    def health_check(self) -> dict[str, Any]:
        """Check cluster health.

        Returns:
            Cluster health information.
        """
        try:
            return self.client.cluster.health()
        except OpenSearchException as e:
            logger.error(f"Health check failed: {e}")
            raise

    def index_exists(self, index: str) -> bool:
        """Check if an index exists.

        Args:
            index: Index name.

        Returns:
            True if index exists, False otherwise.
        """
        return self.client.indices.exists(index=index)

    def create_index(
        self,
        index: str,
        body: dict[str, Any],
        ignore_existing: bool = True,
    ) -> dict[str, Any]:
        """Create an index with the given mapping.

        Args:
            index: Index name.
            body: Index settings and mappings.
            ignore_existing: If True, don't raise error if index exists.

        Returns:
            Index creation response.
        """
        if ignore_existing and self.index_exists(index):
            logger.info(f"Index {index} already exists, skipping creation")
            return {"acknowledged": True, "index": index}

        return self.client.indices.create(index=index, body=body)

    def delete_index(self, index: str, ignore_missing: bool = True) -> dict[str, Any]:
        """Delete an index.

        Args:
            index: Index name.
            ignore_missing: If True, don't raise error if index doesn't exist.

        Returns:
            Index deletion response.
        """
        if ignore_missing and not self.index_exists(index):
            logger.info(f"Index {index} doesn't exist, skipping deletion")
            return {"acknowledged": True}

        return self.client.indices.delete(index=index)

    def index_document(
        self,
        index: str,
        body: dict[str, Any],
        id: Optional[str] = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Index a document.

        Args:
            index: Index name.
            body: Document body.
            id: Optional document ID.
            refresh: If True, refresh index after indexing.

        Returns:
            Index response.
        """
        return self.client.index(
            index=index,
            body=body,
            id=id,
            refresh=refresh,
        )

    def bulk_index(
        self,
        index: str,
        documents: list[dict[str, Any]],
        id_field: str = "id",
        refresh: bool = True,
    ) -> dict[str, Any]:
        """Bulk index multiple documents.

        Args:
            index: Index name.
            documents: List of documents to index.
            id_field: Field to use as document ID.
            refresh: If True, refresh index after bulk operation.

        Returns:
            Bulk response with statistics.
        """
        if not documents:
            return {"errors": False, "items": []}

        body = []
        for doc in documents:
            doc_id = doc.get(id_field)
            action = {"index": {"_index": index}}
            if doc_id:
                action["index"]["_id"] = str(doc_id)
            body.append(action)
            body.append(doc)

        return self.client.bulk(body=body, refresh=refresh)

    def search(
        self,
        index: str,
        body: dict[str, Any],
        size: int = 10,
    ) -> dict[str, Any]:
        """Execute a search query.

        Args:
            index: Index name.
            body: Search query body.
            size: Maximum number of results.

        Returns:
            Search response.
        """
        return self.client.search(index=index, body=body, size=size)

    def knn_search(
        self,
        index: str,
        vector: list[float],
        k: int = 10,
        field: str = "embedding",
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute a k-NN vector search.

        Args:
            index: Index name.
            vector: Query vector.
            k: Number of nearest neighbors to return.
            field: Vector field name.
            filters: Optional filter query.

        Returns:
            Search response with nearest neighbors.
        """
        query = {
            "knn": {
                field: {
                    "vector": vector,
                    "k": k,
                }
            }
        }

        if filters:
            query = {
                "bool": {
                    "must": [query],
                    "filter": [filters],
                }
            }

        body = {"query": query}
        return self.client.search(index=index, body=body, size=k)

    def get_document(
        self,
        index: str,
        id: str,
    ) -> dict[str, Any]:
        """Get a document by ID.

        Args:
            index: Index name.
            id: Document ID.

        Returns:
            Document data.
        """
        return self.client.get(index=index, id=id)

    def delete_document(
        self,
        index: str,
        id: str,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Delete a document by ID.

        Args:
            index: Index name.
            id: Document ID.
            refresh: If True, refresh index after deletion.

        Returns:
            Delete response.
        """
        return self.client.delete(index=index, id=id, refresh=refresh)

    def update_document(
        self,
        index: str,
        id: str,
        body: dict[str, Any],
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Update a document.

        Args:
            index: Index name.
            id: Document ID.
            body: Update body with "doc" or "script".
            refresh: If True, refresh index after update.

        Returns:
            Update response.
        """
        return self.client.update(index=index, id=id, body=body, refresh=refresh)

    def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
