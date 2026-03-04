"""Unit tests for the Bedrock price estimation client.

All tests operate on pure Python logic (_build_prompt, _parse_response,
_calculate_discount) without making real AWS API calls.
"""

import json
from decimal import Decimal

import pytest

from dealfinder.agents.bedrock import BedrockPriceEstimator, PriceEstimationResult, _sanitize
from dealfinder.agents.config import AgentConfig


@pytest.fixture
def estimator() -> BedrockPriceEstimator:
    """BedrockPriceEstimator with test config (no real AWS credentials needed)."""
    config = AgentConfig(
        bedrock_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        discount_threshold=20.0,
        notification_queue_url="",
    )
    return BedrockPriceEstimator(config=config)


class TestBuildPrompt:
    """Tests for BedrockPriceEstimator._build_prompt."""

    def test_prompt_contains_title(self, estimator: BedrockPriceEstimator) -> None:
        """Prompt should include the product title."""
        prompt = estimator._build_prompt(
            title="Sony WH-1000XM5",
            sale_price=Decimal("199.99"),
        )
        assert "Sony WH-1000XM5" in prompt

    def test_prompt_contains_sale_price(self, estimator: BedrockPriceEstimator) -> None:
        """Prompt should include the current sale price."""
        prompt = estimator._build_prompt(
            title="Widget",
            sale_price=Decimal("49.99"),
        )
        assert "49.99" in prompt

    def test_prompt_includes_optional_fields(self, estimator: BedrockPriceEstimator) -> None:
        """Optional brand, category, and description should appear when provided."""
        prompt = estimator._build_prompt(
            title="Headphones",
            sale_price=Decimal("100.00"),
            description="Noise-cancelling",
            category="electronics",
            brand="Bose",
        )
        assert "Bose" in prompt
        assert "electronics" in prompt
        assert "Noise-cancelling" in prompt

    def test_prompt_omits_missing_optional_fields(self, estimator: BedrockPriceEstimator) -> None:
        """Prompt should not contain placeholder text when optional fields are absent."""
        prompt = estimator._build_prompt(
            title="Widget",
            sale_price=Decimal("10.00"),
        )
        assert "Brand:" not in prompt
        assert "Category:" not in prompt
        assert "Description:" not in prompt

    def test_prompt_truncates_long_description(self, estimator: BedrockPriceEstimator) -> None:
        """Descriptions longer than 500 chars should be truncated."""
        long_desc = "x" * 1000
        prompt = estimator._build_prompt(
            title="Widget",
            sale_price=Decimal("10.00"),
            description=long_desc,
        )
        # The inserted description segment should be at most 500 chars
        desc_start = prompt.index("Description: ") + len("Description: ")
        desc_line = prompt[desc_start:].split("\n")[0]
        assert len(desc_line) <= 500

    def test_prompt_requests_json_response(self, estimator: BedrockPriceEstimator) -> None:
        """Prompt should instruct Claude to respond with a JSON object."""
        prompt = estimator._build_prompt(
            title="Widget",
            sale_price=Decimal("10.00"),
        )
        assert "estimated_price" in prompt
        assert "confidence" in prompt


class TestParseResponse:
    """Tests for BedrockPriceEstimator._parse_response."""

    def test_parses_clean_json(self, estimator: BedrockPriceEstimator) -> None:
        """Valid JSON response should be parsed correctly."""
        response = json.dumps({
            "estimated_price": 299.99,
            "confidence": 0.85,
            "range_low": 250.00,
            "range_high": 350.00,
            "reasoning": "Popular consumer electronics item.",
        })
        data = estimator._parse_response(response)
        assert data["estimated_price"] == 299.99
        assert data["confidence"] == 0.85

    def test_parses_json_in_markdown_fence(self, estimator: BedrockPriceEstimator) -> None:
        """JSON wrapped in markdown code fences should be extracted and parsed."""
        response = (
            "```json\n"
            '{"estimated_price": 199.99, "confidence": 0.9, '
            '"range_low": 180.0, "range_high": 220.0, "reasoning": "ok"}\n'
            "```"
        )
        data = estimator._parse_response(response)
        assert data["estimated_price"] == 199.99
        assert data["confidence"] == 0.9

    def test_raises_on_no_json(self, estimator: BedrockPriceEstimator) -> None:
        """Plain text with no JSON object should raise ValueError."""
        with pytest.raises(ValueError, match="No JSON object"):
            estimator._parse_response("I cannot determine the price.")

    def test_raises_on_missing_estimated_price(self, estimator: BedrockPriceEstimator) -> None:
        """Response missing estimated_price should raise ValueError."""
        response = json.dumps({"confidence": 0.8})
        with pytest.raises(ValueError, match="Missing required fields"):
            estimator._parse_response(response)

    def test_raises_on_missing_confidence(self, estimator: BedrockPriceEstimator) -> None:
        """Response missing confidence should raise ValueError."""
        response = json.dumps({"estimated_price": 100.0})
        with pytest.raises(ValueError, match="Missing required fields"):
            estimator._parse_response(response)

    def test_raises_on_confidence_above_one(self, estimator: BedrockPriceEstimator) -> None:
        """Confidence > 1.0 should raise ValueError."""
        response = json.dumps({"estimated_price": 100.0, "confidence": 1.5})
        with pytest.raises(ValueError, match="outside 0.0"):
            estimator._parse_response(response)

    def test_raises_on_negative_confidence(self, estimator: BedrockPriceEstimator) -> None:
        """Negative confidence should raise ValueError."""
        response = json.dumps({"estimated_price": 100.0, "confidence": -0.1})
        with pytest.raises(ValueError, match="outside 0.0"):
            estimator._parse_response(response)

    def test_boundary_confidence_zero(self, estimator: BedrockPriceEstimator) -> None:
        """Confidence of exactly 0.0 should be accepted."""
        response = json.dumps({"estimated_price": 100.0, "confidence": 0.0})
        data = estimator._parse_response(response)
        assert data["confidence"] == 0.0

    def test_boundary_confidence_one(self, estimator: BedrockPriceEstimator) -> None:
        """Confidence of exactly 1.0 should be accepted."""
        response = json.dumps({"estimated_price": 100.0, "confidence": 1.0})
        data = estimator._parse_response(response)
        assert data["confidence"] == 1.0

    def test_optional_range_fields_absent(self, estimator: BedrockPriceEstimator) -> None:
        """Response without range_low / range_high should still parse."""
        response = json.dumps({"estimated_price": 50.0, "confidence": 0.7})
        data = estimator._parse_response(response)
        assert data.get("range_low") is None
        assert data.get("range_high") is None


class TestPriceEstimationResult:
    """Tests for PriceEstimationResult dataclass."""

    def test_result_fields(self) -> None:
        """All fields should be accessible and typed correctly."""
        result = PriceEstimationResult(
            estimated_price=Decimal("299.99"),
            confidence=Decimal("0.850"),
            range_low=Decimal("250.00"),
            range_high=Decimal("350.00"),
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            inference_time_ms=450,
        )
        assert result.estimated_price == Decimal("299.99")
        assert result.confidence == Decimal("0.850")
        assert result.range_low == Decimal("250.00")
        assert result.range_high == Decimal("350.00")
        assert result.inference_time_ms == 450

    def test_result_nullable_range(self) -> None:
        """range_low and range_high should accept None."""
        result = PriceEstimationResult(
            estimated_price=Decimal("100.00"),
            confidence=Decimal("0.600"),
            range_low=None,
            range_high=None,
            model_id="model",
            inference_time_ms=200,
        )
        assert result.range_low is None
        assert result.range_high is None


class TestSanitize:
    """Tests for the module-level _sanitize helper."""

    def test_strips_newlines(self) -> None:
        """Newline characters should be replaced with spaces."""
        assert _sanitize("foo\nbar") == "foo bar"

    def test_strips_carriage_returns(self) -> None:
        """Carriage return characters should be replaced with spaces."""
        assert _sanitize("foo\rbar") == "foo bar"

    def test_truncates_to_default_max_len(self) -> None:
        """Input longer than 500 chars should be truncated to 500."""
        assert len(_sanitize("x" * 1000)) == 500

    def test_truncates_to_custom_max_len(self) -> None:
        """Custom max_len should be respected."""
        assert len(_sanitize("x" * 100, max_len=50)) == 50

    def test_short_clean_string_unchanged(self) -> None:
        """Input shorter than max_len with no special characters is returned as-is."""
        assert _sanitize("Sony Headphones") == "Sony Headphones"


class TestBuildPromptSanitization:
    """Tests that _build_prompt sanitizes untrusted RSS content before interpolation."""

    def test_newlines_stripped_from_title(self, estimator: BedrockPriceEstimator) -> None:
        """Newlines in title should be replaced with spaces to prevent prompt injection."""
        prompt = estimator._build_prompt(
            title="Widget\nFake instruction",
            sale_price=Decimal("10.00"),
        )
        assert "Widget Fake instruction" in prompt
        assert "Widget\nFake instruction" not in prompt

    def test_newlines_stripped_from_description(self, estimator: BedrockPriceEstimator) -> None:
        """Newlines in description should be replaced with spaces."""
        prompt = estimator._build_prompt(
            title="Widget",
            sale_price=Decimal("10.00"),
            description="Legit desc\nFake instruction",
        )
        assert "Legit desc Fake instruction" in prompt
        assert "Legit desc\nFake instruction" not in prompt

    def test_newlines_stripped_from_brand(self, estimator: BedrockPriceEstimator) -> None:
        """Newlines in brand should be replaced with spaces."""
        prompt = estimator._build_prompt(
            title="Widget",
            sale_price=Decimal("10.00"),
            brand="Acme\nInjected",
        )
        assert "Acme Injected" in prompt
        assert "Acme\nInjected" not in prompt
