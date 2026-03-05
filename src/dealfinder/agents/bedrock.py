"""AWS Bedrock client for deal price estimation and search enrichment using Claude.

Provides:
- Price estimation for RSS-discovered deals (BedrockPriceEstimator)
- Search result enrichment via Tavily + Bedrock pipeline (BedrockSearchExtractor)
"""

import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

from dealfinder.agents.config import AgentConfig

if TYPE_CHECKING:
    from dealfinder.api.schemas import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class PriceEstimationResult:
    """Result from a Bedrock price estimation call.

    Attributes:
        estimated_price: Estimated fair market retail value.
        confidence: Confidence score in the estimate, 0.0–1.0.
        range_low: Lower bound of the estimated price range.
        range_high: Upper bound of the estimated price range.
        model_id: Bedrock model ID used for inference.
        inference_time_ms: Wall-clock inference duration in milliseconds.
    """

    estimated_price: Decimal
    confidence: Decimal
    range_low: Decimal | None
    range_high: Decimal | None
    model_id: str
    inference_time_ms: int


def _sanitize(value: str, max_len: int = 500) -> str:
    """Strip whitespace control characters and truncate to prevent prompt injection.

    Replaces newlines, carriage returns, horizontal tabs, and Unicode line/paragraph
    separators (U+2028, U+2029) with spaces, then truncates to max_len characters.

    Args:
        value: Input string from an untrusted source (e.g. an RSS feed field).
        max_len: Maximum number of characters to retain after truncation.

    Returns:
        Sanitized string safe for Claude prompt interpolation.
    """
    return (
        value[:max_len]
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
        .replace("\u2028", " ")
        .replace("\u2029", " ")
    )


class BedrockPriceEstimator:
    """Estimates fair market prices for deals using AWS Bedrock (Claude).

    Invokes Claude via the Bedrock runtime API with a structured prompt
    and parses the JSON response to extract pricing data. The client is
    initialised lazily so unit tests can instantiate it without AWS creds.

    Example:
        estimator = BedrockPriceEstimator()
        result = estimator.estimate_price(
            title="Sony WH-1000XM5 Headphones",
            sale_price=Decimal("199.99"),
            category="electronics",
        )
        print(result.estimated_price, result.confidence)
    """

    MODEL_VERSION = "1.0"

    def __init__(self, config: AgentConfig | None = None) -> None:
        """Initialise the Bedrock price estimator.

        Args:
            config: Agent configuration. Loaded from environment if not provided.
        """
        self.config = config or AgentConfig()
        self._client = None

    @property
    def client(self):
        """Lazily initialise the Bedrock runtime boto3 client."""
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.bedrock_region,
            )
        return self._client

    def _build_prompt(
        self,
        title: str,
        sale_price: Decimal,
        description: str | None = None,
        category: str | None = None,
        brand: str | None = None,
    ) -> str:
        """Build a structured price estimation prompt for Claude.

        Args:
            title: Product title or name.
            sale_price: Current sale price of the item.
            description: Optional product description (sanitized and truncated to 500 chars).
            category: Optional product category.
            brand: Optional brand name.

        Returns:
            Formatted prompt string ready to be sent to Claude.
        """
        lines = [
            "You are a pricing expert. Estimate the fair market retail price for this product.",
            "",
            f"Product: {_sanitize(title)}",
        ]
        if brand:
            lines.append(f"Brand: {_sanitize(brand)}")
        if category:
            lines.append(f"Category: {_sanitize(category)}")
        if description:
            lines.append(f"Description: {_sanitize(description)}")
        lines.append(f"Current sale price: ${sale_price}")
        lines.extend([
            "",
            "Respond with ONLY a JSON object (no markdown, no explanation):",
            '{"estimated_price": <number>, "confidence": <0.0-1.0>,'
            ' "range_low": <number>, "range_high": <number>, "reasoning": "<brief>"}',
        ])
        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> dict:
        """Parse the JSON price estimate from a Claude response.

        Handles responses that wrap JSON in markdown code fences.

        Args:
            response_text: Raw text content from the Claude response.

        Returns:
            Parsed response dict with at minimum estimated_price and confidence.

        Raises:
            ValueError: If no JSON object is found or required fields are missing.
            ValueError: If confidence is outside the 0.0–1.0 range.
        """
        start = response_text.find("{")
        if start == -1:
            raise ValueError(f"No JSON object in response: {response_text[:200]}")

        try:
            data, _ = json.JSONDecoder().raw_decode(response_text, start)
        except json.JSONDecodeError:
            raise ValueError(f"No JSON object in response: {response_text[:200]}")

        missing = {"estimated_price", "confidence"} - data.keys()
        if missing:
            raise ValueError(f"Missing required fields in response: {missing}")

        estimated_price = float(data["estimated_price"])
        if estimated_price <= 0:
            raise ValueError(f"estimated_price must be positive, got {estimated_price}")

        confidence = float(data["confidence"])
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence {confidence} outside 0.0–1.0 range")

        return data

    def estimate_price(
        self,
        title: str,
        sale_price: Decimal,
        description: str | None = None,
        category: str | None = None,
        brand: str | None = None,
    ) -> PriceEstimationResult:
        """Estimate the fair market price for a deal using Claude.

        Args:
            title: Product title.
            sale_price: Current sale price.
            description: Optional product description.
            category: Optional product category.
            brand: Optional brand name.

        Returns:
            PriceEstimationResult with estimated price, confidence, and range.

        Raises:
            ClientError: If the Bedrock API call fails.
            ValueError: If the Claude response cannot be parsed as valid price data.
        """
        prompt = self._build_prompt(title, sale_price, description, category, brand)
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 256,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}],
        })

        start_ms = int(time.time() * 1000)

        try:
            response = self.client.invoke_model(
                modelId=self.config.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            logger.error(f"Bedrock API error [{code}]: {msg}")
            raise

        inference_ms = int(time.time() * 1000) - start_ms

        response_body = json.loads(response["body"].read())
        content_blocks = response_body.get("content", [])
        if not content_blocks or content_blocks[0].get("type") != "text":
            raise ValueError(f"Unexpected Bedrock response structure: {response_body}")
        response_text = content_blocks[0]["text"]

        data = self._parse_response(response_text)

        return PriceEstimationResult(
            estimated_price=Decimal(str(data["estimated_price"])).quantize(Decimal("0.01")),
            confidence=Decimal(str(data["confidence"])).quantize(Decimal("0.001")),
            range_low=(
                Decimal(str(data["range_low"])).quantize(Decimal("0.01"))
                if data.get("range_low") is not None
                else None
            ),
            range_high=(
                Decimal(str(data["range_high"])).quantize(Decimal("0.01"))
                if data.get("range_high") is not None
                else None
            ),
            model_id=self.config.bedrock_model_id,
            inference_time_ms=inference_ms,
        )


class BedrockSearchExtractor:
    """Enriches Tavily web search results using Claude via AWS Bedrock.

    Takes raw Tavily result snippets and uses Claude to extract clean product
    data (title, URL, current price) and assign a deal quality score (0–10)
    with a brief reasoning explanation. All fields are extracted in a single
    Bedrock call to minimise latency and cost.

    This is the agentic layer of the search pipeline — Claude applies market
    knowledge to judge deal quality, making the scores extensible to richer
    reasoning (price comparison, trend analysis) in future phases.

    Example:
        extractor = BedrockSearchExtractor()
        results = extractor.extract(tavily_results)
        for r in results:
            print(r.title, r.current_price, r.quality_score)
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        """Initialise the search extractor.

        Args:
            config: Agent configuration. Loaded from environment if not provided.
        """
        self.config = config or AgentConfig()
        self._client = None

    @property
    def client(self):
        """Lazily initialise the Bedrock runtime boto3 client."""
        if self._client is None:
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.bedrock_region,
            )
        return self._client

    def _build_extraction_prompt(self, results: list[dict]) -> str:
        """Build a structured extraction + quality scoring prompt for Claude.

        Args:
            results: List of raw Tavily result dicts with title, url, content keys.

        Returns:
            Formatted prompt string ready to be sent to Claude.
        """
        condensed = [
            {
                "title": _sanitize(r.get("title", ""), max_len=200),
                "url": r.get("url", ""),
                "content": _sanitize(r.get("content", ""), max_len=400),
            }
            for r in results
        ]
        results_json = json.dumps(condensed, indent=2)
        return (
            "You are a deal analysis assistant. Given these web search result snippets, "
            "extract and score each result as a potential product deal.\n\n"
            "For each result return:\n"
            "- title: Clean product name (remove store names and marketing filler)\n"
            "- url: The product URL exactly as provided\n"
            "- current_price: Current sale price as a string (e.g. \"$279.99\") or null if not found\n"
            "- quality_score: Float 0.0–10.0 rating the deal quality\n"
            "  (10 = exceptional value vs typical retail, 0 = poor value or no deal)\n"
            "  Base this on: price vs known typical retail, brand reputation, discount signals\n"
            "- quality_reason: Max 15-word explanation of the score\n\n"
            f"Search results:\n{results_json}\n\n"
            "Respond with ONLY a JSON array — no markdown, no explanation:\n"
            '[{"title": "...", "url": "...", "current_price": "...", '
            '"quality_score": 7.5, "quality_reason": "..."}]'
        )

    def _parse_extraction_response(self, response_text: str, original: list[dict]) -> list:
        """Parse Claude's JSON array response into SearchResult-compatible dicts.

        Falls back to minimal results (title/url only) if parsing fails.

        Args:
            response_text: Raw Claude output.
            original: Original Tavily results used as fallback source for title/url.

        Returns:
            List of dicts with title, url, current_price, quality_score, quality_reason keys.
        """
        start = response_text.find("[")
        if start != -1:
            try:
                data, _ = json.JSONDecoder().raw_decode(response_text, start)
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, ValueError):
                pass
        logger.warning("BedrockSearchExtractor: failed to parse Claude response; using fallbacks")
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""),
             "current_price": None, "quality_score": None, "quality_reason": None}
            for r in original
        ]

    def extract(self, results: list[dict]) -> list[dict]:
        """Extract and score product data from Tavily search results via Claude.

        Args:
            results: List of raw Tavily result dicts (title, url, content).

        Returns:
            List of enriched result dicts with title, url, current_price,
            quality_score, and quality_reason fields.

        Raises:
            ClientError: If the Bedrock API call fails.
        """
        if not results:
            return []

        prompt = self._build_extraction_prompt(results)
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}],
        })

        try:
            response = self.client.invoke_model(
                modelId=self.config.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
        except ClientError as e:
            code = e.response["Error"]["Code"]
            msg = e.response["Error"]["Message"]
            logger.error(f"BedrockSearchExtractor API error [{code}]: {msg}")
            raise

        response_body = json.loads(response["body"].read())
        content_blocks = response_body.get("content", [])
        if not content_blocks or content_blocks[0].get("type") != "text":
            logger.warning("BedrockSearchExtractor: unexpected response structure")
            return self._parse_extraction_response("", results)

        response_text = content_blocks[0]["text"]
        extracted = self._parse_extraction_response(response_text, results)
        logger.info(f"BedrockSearchExtractor: enriched {len(extracted)} results")
        return extracted
