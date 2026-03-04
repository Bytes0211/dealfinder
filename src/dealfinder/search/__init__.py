"""Search module for Deal Finder.

This module provides OpenSearch integration for vector-based
semantic search of deals.
"""

from dealfinder.search.client import OpenSearchClient, OpenSearchConfig
from dealfinder.search.index import DealIndex, IndexManager
from dealfinder.search.embeddings import EmbeddingService

__all__ = [
    "OpenSearchClient",
    "OpenSearchConfig",
    "DealIndex",
    "IndexManager",
    "EmbeddingService",
]
