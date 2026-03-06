"""Unit tests for search index module."""

import pytest

from dealfinder.search.index import DealIndex


class TestDealIndex:
    """Tests for DealIndex configuration."""

    def test_index_name(self):
        """Test default index name."""
        assert DealIndex.NAME == "deals"

    def test_vector_field(self):
        """Test vector field name."""
        assert DealIndex.VECTOR_FIELD == "embedding"

    def test_default_vector_dimension(self):
        """Test default vector dimension."""
        assert DealIndex.VECTOR_DIMENSION == 1536

    def test_get_mapping_returns_dict(self):
        """Test get_mapping returns a dictionary."""
        mapping = DealIndex.get_mapping()

        assert isinstance(mapping, dict)
        assert "settings" in mapping
        assert "mappings" in mapping

    def test_get_mapping_has_settings(self):
        """Test mapping has required settings."""
        mapping = DealIndex.get_mapping()
        settings = mapping["settings"]["index"]

        assert "number_of_shards" in settings
        assert "number_of_replicas" in settings
        assert settings["knn"] is True

    def test_get_mapping_has_properties(self):
        """Test mapping has required properties."""
        mapping = DealIndex.get_mapping()
        properties = mapping["mappings"]["properties"]

        # Check identifier fields
        assert properties["id"]["type"] == "keyword"
        assert properties["deal_id"]["type"] == "keyword"
        assert properties["source_id"]["type"] == "keyword"
        assert properties["external_id"]["type"] == "keyword"

        # Check text fields
        assert properties["title"]["type"] == "text"
        assert properties["description"]["type"] == "text"
        assert properties["url"]["type"] == "keyword"

        # Check pricing fields
        assert properties["original_price"]["type"] == "float"
        assert properties["sale_price"]["type"] == "float"
        assert properties["discount_percentage"]["type"] == "float"

        assert properties["brand"]["type"] == "keyword"
        assert properties["tags"]["type"] == "keyword"

        # Check status fields
        assert properties["status"]["type"] == "keyword"
        assert properties["is_high_value"]["type"] == "boolean"

        # Check timestamp fields
        assert properties["discovered_at"]["type"] == "date"
        assert properties["created_at"]["type"] == "date"
        assert properties["updated_at"]["type"] == "date"

    def test_get_mapping_has_vector_field(self):
        """Test mapping has vector field with k-NN configuration."""
        mapping = DealIndex.get_mapping()
        vector_field = mapping["mappings"]["properties"]["embedding"]

        assert vector_field["type"] == "knn_vector"
        assert vector_field["dimension"] == 1536
        assert vector_field["method"]["name"] == "hnsw"
        assert vector_field["method"]["space_type"] == "cosinesimil"
        assert vector_field["method"]["engine"] == "nmslib"

    def test_get_mapping_custom_dimension(self):
        """Test get_mapping with custom vector dimension."""
        mapping = DealIndex.get_mapping(vector_dimension=768)
        vector_field = mapping["mappings"]["properties"]["embedding"]

        assert vector_field["dimension"] == 768

    def test_get_mapping_has_analyzer(self):
        """Test mapping has custom analyzer."""
        mapping = DealIndex.get_mapping()
        analyzers = mapping["settings"]["analysis"]["analyzer"]

        assert "deal_analyzer" in analyzers
        assert analyzers["deal_analyzer"]["type"] == "custom"
        assert "lowercase" in analyzers["deal_analyzer"]["filter"]

    def test_title_uses_deal_analyzer(self):
        """Test title field uses deal analyzer."""
        mapping = DealIndex.get_mapping()
        title_field = mapping["mappings"]["properties"]["title"]

        assert title_field["analyzer"] == "deal_analyzer"

    def test_title_has_keyword_subfield(self):
        """Test title has keyword subfield for exact matching."""
        mapping = DealIndex.get_mapping()
        title_field = mapping["mappings"]["properties"]["title"]

        assert "fields" in title_field
        assert title_field["fields"]["keyword"]["type"] == "keyword"
