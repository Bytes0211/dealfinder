"""Index management for OpenSearch.

This module provides index creation and management utilities
for the deals index with k-NN vector search capabilities.
"""

import logging
from typing import Any, Optional

from dealfinder.search.client import OpenSearchClient, OpenSearchConfig

logger = logging.getLogger(__name__)


class DealIndex:
    """Index configuration for deals."""

    NAME = "deals"
    VECTOR_FIELD = "embedding"
    VECTOR_DIMENSION = 1536  # OpenAI ada-002

    @classmethod
    def get_mapping(cls, vector_dimension: Optional[int] = None) -> dict[str, Any]:
        """Get the index mapping for deals.

        Args:
            vector_dimension: Override default vector dimension.

        Returns:
            Index mapping configuration.
        """
        dim = vector_dimension or cls.VECTOR_DIMENSION

        return {
            "settings": {
                "index": {
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                    "knn": True,  # Enable k-NN plugin
                    "knn.algo_param.ef_search": 100,
                },
                "analysis": {
                    "analyzer": {
                        "deal_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": ["lowercase", "asciifolding", "stop"],
                        }
                    }
                },
            },
            "mappings": {
                "properties": {
                    # Identifiers
                    "id": {"type": "keyword"},
                    "deal_id": {"type": "keyword"},
                    "source_id": {"type": "keyword"},
                    "external_id": {"type": "keyword"},
                    # Text fields
                    "title": {
                        "type": "text",
                        "analyzer": "deal_analyzer",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "description": {
                        "type": "text",
                        "analyzer": "deal_analyzer",
                    },
                    "url": {"type": "keyword"},
                    # Pricing
                    "original_price": {"type": "float"},
                    "sale_price": {"type": "float"},
                    "estimated_value": {"type": "float"},
                    "discount_percentage": {"type": "float"},
                    "currency": {"type": "keyword"},
                    "brand": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    # Status
                    "status": {"type": "keyword"},
                    "confidence_score": {"type": "float"},
                    "is_high_value": {"type": "boolean"},
                    # Timestamps
                    "discovered_at": {"type": "date"},
                    "evaluated_at": {"type": "date"},
                    "expires_at": {"type": "date"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    # Vector embedding for semantic search
                    cls.VECTOR_FIELD: {
                        "type": "knn_vector",
                        "dimension": dim,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 16,
                            },
                        },
                    },
                }
            },
        }


class IndexManager:
    """Manager for OpenSearch index operations.

    Example:
        manager = IndexManager()
        manager.create_deals_index()
        manager.refresh_index("deals")
    """

    def __init__(
        self,
        client: Optional[OpenSearchClient] = None,
        config: Optional[OpenSearchConfig] = None,
    ):
        """Initialize index manager.

        Args:
            client: OpenSearch client instance.
            config: OpenSearch configuration if client not provided.
        """
        if client is None:
            client = OpenSearchClient(config)
        self.client = client

    def create_deals_index(
        self,
        vector_dimension: Optional[int] = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Create the deals index with k-NN mapping.

        Args:
            vector_dimension: Override default vector dimension.
            force: If True, delete existing index first.

        Returns:
            Index creation response.
        """
        if force:
            self.client.delete_index(DealIndex.NAME, ignore_missing=True)

        mapping = DealIndex.get_mapping(vector_dimension)
        return self.client.create_index(
            index=DealIndex.NAME,
            body=mapping,
            ignore_existing=True,
        )

    def delete_deals_index(self) -> dict[str, Any]:
        """Delete the deals index.

        Returns:
            Index deletion response.
        """
        return self.client.delete_index(DealIndex.NAME, ignore_missing=True)

    def refresh_index(self, index: str = DealIndex.NAME) -> dict[str, Any]:
        """Refresh an index to make recent changes searchable.

        Args:
            index: Index name.

        Returns:
            Refresh response.
        """
        return self.client.client.indices.refresh(index=index)

    def get_index_stats(self, index: str = DealIndex.NAME) -> dict[str, Any]:
        """Get index statistics.

        Args:
            index: Index name.

        Returns:
            Index statistics.
        """
        return self.client.client.indices.stats(index=index)

    def get_index_mapping(self, index: str = DealIndex.NAME) -> dict[str, Any]:
        """Get index mapping.

        Args:
            index: Index name.

        Returns:
            Index mapping.
        """
        return self.client.client.indices.get_mapping(index=index)

    def update_index_settings(
        self,
        index: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        """Update index settings.

        Args:
            index: Index name.
            settings: New settings to apply.

        Returns:
            Update response.
        """
        return self.client.client.indices.put_settings(
            index=index,
            body={"settings": settings},
        )

    def reindex(
        self,
        source_index: str,
        dest_index: str,
        query: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Reindex documents from source to destination.

        Args:
            source_index: Source index name.
            dest_index: Destination index name.
            query: Optional query to filter documents.

        Returns:
            Reindex response.
        """
        body = {
            "source": {"index": source_index},
            "dest": {"index": dest_index},
        }
        if query:
            body["source"]["query"] = query

        return self.client.client.reindex(body=body)
