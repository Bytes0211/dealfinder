"""EvaluatorAgent Lambda function for deal price evaluation.

Fetches a discovered deal from Aurora, estimates fair market price via
AWS Bedrock (Claude), calculates the discount percentage, and marks
high-value deals so they can be forwarded to the notification stage.
"""

import asyncio
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from dealfinder.agents.bedrock import BedrockPriceEstimator, PriceEstimationResult
from dealfinder.agents.config import AgentConfig
from dealfinder.data.repository import DealRepository, PriceEstimateRepository
from dealfinder.db.connection import get_async_session
from dealfinder.db.models import DealStatus, PriceEstimate

logger = logging.getLogger(__name__)

class EvaluatorAgent:
    """Evaluates deals by estimating fair market price and calculating discounts.

    For each deal the agent:
    1. Marks the deal as EVALUATING.
    2. Calls Bedrock (Claude) to estimate the fair market retail price.
    3. Stores a PriceEstimate row with the result.
    4. Calculates the discount percentage.
    5. Marks the deal as EVALUATED and sets is_high_value if the discount
       meets or exceeds the configured threshold.

    Deals with no price data or for which estimation fails are REJECTED.

    Example:
        evaluator = EvaluatorAgent()
        result = asyncio.run(evaluator.evaluate_deal(deal_id))
        print(result["is_high_value"], result["discount_percentage"])
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        estimator: BedrockPriceEstimator | None = None,
    ) -> None:
        """Initialise the evaluator agent.

        Args:
            config: Agent configuration. Loaded from environment if not provided.
            estimator: Bedrock price estimator. Created from config if not provided.
        """
        self.config = config or AgentConfig()
        self.estimator = estimator or BedrockPriceEstimator(self.config)

    def _calculate_discount(
        self, sale_price: Decimal, estimated_value: Decimal
    ) -> Decimal:
        """Calculate the discount percentage relative to estimated market value.

        Args:
            sale_price: Current sale price.
            estimated_value: Estimated fair market retail value.

        Returns:
            Discount percentage in the range 0–100 (two decimal places).
            Returns Decimal("0") if estimated_value is zero or negative.
        """
        if estimated_value <= 0:
            return Decimal("0")
        discount = ((estimated_value - sale_price) / estimated_value) * 100
        return max(Decimal("0"), discount).quantize(Decimal("0.01"))

    async def evaluate_deal(self, deal_id: UUID) -> dict:
        """Evaluate a single deal and persist the price estimate.

        Args:
            deal_id: UUID of the deal to evaluate.

        Returns:
            Dictionary with:
                deal_id: String UUID of the evaluated deal.
                status: One of "evaluated", "rejected", "not_found", "estimation_failed".
                is_high_value: True if the discount meets the threshold.
                discount_percentage: Calculated discount (float, 0 if not evaluated).
                estimated_value: Bedrock estimated price (float, 0 if not evaluated).
                confidence: Bedrock confidence score (float, 0 if not evaluated).
        """
        async with get_async_session() as session:
            deal_repo = DealRepository(session)
            estimate_repo = PriceEstimateRepository(session)

            deal = await deal_repo.get_by_id(deal_id)
            if not deal:
                logger.warning(f"Deal not found: {deal_id}")
                return {
                    "deal_id": str(deal_id),
                    "status": "not_found",
                    "is_high_value": False,
                    "discount_percentage": 0.0,
                    "estimated_value": 0.0,
                    "confidence": 0.0,
                }

            await deal_repo.update_status(deal_id, DealStatus.EVALUATING)

            sale_price = deal.sale_price or deal.original_price
            if not sale_price:
                logger.warning(f"Deal {deal_id} has no price data — rejecting")
                await deal_repo.update_status(deal_id, DealStatus.REJECTED)
                return {
                    "deal_id": str(deal_id),
                    "status": "rejected",
                    "is_high_value": False,
                    "discount_percentage": 0.0,
                    "estimated_value": 0.0,
                    "confidence": 0.0,
                }

            try:
                loop = asyncio.get_running_loop()
                result: PriceEstimationResult = await loop.run_in_executor(
                    None,
                    lambda: self.estimator.estimate_price(
                        title=deal.title,
                        sale_price=sale_price,
                        description=deal.description,
                        category=deal.category,
                        brand=deal.brand,
                    ),
                )
            except Exception as e:
                logger.error(f"Bedrock estimation failed for deal {deal_id}: {e}")
                await deal_repo.update_status(deal_id, DealStatus.REJECTED)
                return {
                    "deal_id": str(deal_id),
                    "status": "estimation_failed",
                    "is_high_value": False,
                    "discount_percentage": 0.0,
                    "estimated_value": 0.0,
                    "confidence": 0.0,
                }

            estimate = PriceEstimate(
                deal_id=deal_id,
                model_name=result.model_id,
                model_version=BedrockPriceEstimator.MODEL_VERSION,
                estimated_price=result.estimated_price,
                confidence=result.confidence,
                prediction_range_low=result.range_low,
                prediction_range_high=result.range_high,
                inference_time_ms=result.inference_time_ms,
                features_used={"title": deal.title, "category": deal.category},
            )
            await estimate_repo.create(estimate)

            discount = self._calculate_discount(sale_price, result.estimated_price)
            is_high_value = discount >= Decimal(str(self.config.discount_threshold))

            if is_high_value:
                await deal_repo.mark_as_high_value(
                    deal_id,
                    float(result.estimated_price),
                    float(result.confidence),
                )

            updated_deal = await deal_repo.update_status(deal_id, DealStatus.EVALUATED)
            if updated_deal:
                updated_deal.discount_percentage = discount
                await session.flush()

            logger.info(
                f"Evaluated deal {deal_id}: ${sale_price} → est. ${result.estimated_price} "
                f"({discount}% discount, high_value={is_high_value})"
            )

        return {
            "deal_id": str(deal_id),
            "status": "evaluated",
            "is_high_value": is_high_value,
            "discount_percentage": float(discount),
            "estimated_value": float(result.estimated_price),
            "confidence": float(result.confidence),
        }

    async def run(self, event: dict) -> dict:
        """Process a Step Functions evaluation event.

        Args:
            event: Step Functions event. Must contain a ``deal_id`` string key.

        Returns:
            Evaluation result dictionary for the Step Functions state machine.

        Raises:
            ValueError: If event does not contain a deal_id.
        """
        deal_id_str = event.get("deal_id")
        if not deal_id_str:
            raise ValueError("event.deal_id is required")
        return await self.evaluate_deal(UUID(deal_id_str))


def handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point for the Evaluator Agent.

    Args:
        event: Step Functions event with a ``deal_id`` key.
        context: Lambda execution context (unused).

    Returns:
        Evaluation result with deal_id, is_high_value, and discount_percentage.
    """
    return asyncio.run(EvaluatorAgent().run(event))
