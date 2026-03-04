"""AWS Bedrock client for deal price estimation using Claude.

Provides price estimation for deals by invoking AWS Bedrock with
structured prompts and parsing structured JSON responses from Claude.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from dealfinder.agents.config import AgentConfig

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
            description: Optional product description (truncated to 500 chars).
            category: Optional product category.
            brand: Optional brand name.

        Returns:
            Formatted prompt string ready to be sent to Claude.
        """
        lines = [
            "You are a pricing expert. Estimate the fair market retail price for this product.",
            "",
            f"Product: {title}",
        ]
        if brand:
            lines.append(f"Brand: {brand}")
        if category:
            lines.append(f"Category: {category}")
        if description:
            lines.append(f"Description: {description[:500]}")
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
        match = re.search(r"\{.*\}", response_text.strip(), re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object in response: {response_text[:200]}")

        data = json.loads(match.group())

        missing = {"estimated_price", "confidence"} - data.keys()
        if missing:
            raise ValueError(f"Missing required fields in response: {missing}")

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
        response_text = response_body["content"][0]["text"]

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
