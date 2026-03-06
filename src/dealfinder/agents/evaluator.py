"""EvaluatorAgent Lambda function for deal price evaluation.

Fetches a discovered deal from Aurora, estimates fair market price via
AWS Bedrock (Claude), calculates the discount percentage, and marks
high-value deals so they can be forwarded to the notification stage.
"""

import asyncio
import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from dealfinder.agents.bedrock import BedrockPriceEstimator, PriceEstimationResult
from dealfinder.agents.config import AgentConfig
from dealfinder.data.repository import DealRepository, PriceEstimateRepository, UserRepository
from dealfinder.db.connection import get_async_session
from dealfinder.db.models import Deal, DealStatus, PriceEstimate

logger = logging.getLogger(__name__)

_TRANSIENT_BEDROCK_CODES: frozenset[str] = frozenset({
    "ThrottlingException",
    "ServiceUnavailableException",
    "ModelTimeoutException",
    "InternalServerException",
})


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

        Raises:
            ClientError: Re-raised for transient Bedrock errors (ThrottlingException,
                ServiceUnavailableException, ModelTimeoutException,
                InternalServerException) so the Step Functions EvaluateDeal
                Retry block can handle them.
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
                    "matched_feed_pairs": [],
                }

            await deal_repo.update_status(deal_id, DealStatus.EVALUATING)

            sale_price = deal.sale_price if deal.sale_price is not None else deal.original_price
            if sale_price is None:
                logger.warning(f"Deal {deal_id} has no price data — rejecting")
                await deal_repo.update_status(deal_id, DealStatus.REJECTED)
                return {
                    "deal_id": str(deal_id),
                    "status": "rejected",
                    "is_high_value": False,
                    "discount_percentage": 0.0,
                    "estimated_value": 0.0,
                    "confidence": 0.0,
                    "matched_feed_pairs": [],
                }

            try:
                loop = asyncio.get_running_loop()
                result: PriceEstimationResult = await loop.run_in_executor(
                    None,
                    lambda: self.estimator.estimate_price(
                        title=deal.title,
                        sale_price=sale_price,
                        description=deal.description,
                        brand=deal.brand,
                    ),
                )
            except ClientError as e:
                if e.response["Error"]["Code"] in _TRANSIENT_BEDROCK_CODES:
                    await deal_repo.update_status(deal_id, DealStatus.DISCOVERED)
                    raise  # let Step Functions retry via EvaluateDeal Retry block
                logger.error(f"Bedrock estimation failed for deal {deal_id}: {e}")
                await deal_repo.update_status(deal_id, DealStatus.REJECTED)
                return {
                    "deal_id": str(deal_id),
                    "status": "estimation_failed",
                    "is_high_value": False,
                    "discount_percentage": 0.0,
                    "estimated_value": 0.0,
                    "confidence": 0.0,
                    "matched_feed_pairs": [],
                }
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
                    "matched_feed_pairs": [],
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
                features_used={
                    "title": deal.title,
                    "brand": deal.brand,
                    "description": deal.description[:500] if deal.description else None,
                },
            )
            await estimate_repo.create(estimate)

            discount = self._calculate_discount(sale_price, result.estimated_price)
            is_high_value = discount >= Decimal(str(self.config.discount_threshold))

            if is_high_value:
                await deal_repo.mark_as_high_value(
                    deal_id,
                    result.estimated_price,
                    result.confidence,
                )

            updated_deal = await deal_repo.update_status(deal_id, DealStatus.EVALUATED)
            if updated_deal is None:
                raise RuntimeError(
                    f"Deal {deal_id} vanished during evaluation — possible concurrent deletion"
                )
            updated_deal.discount_percentage = discount
            await session.flush()

            logger.info(
                f"Evaluated deal {deal_id}: ${sale_price} → est. ${result.estimated_price} "
                f"({discount}% discount, high_value={is_high_value})"
            )

        # Match evaluated deal against all users' watchlist feeds and notify
        matched_feed_pairs: list[dict] = []
        if is_high_value or discount > 0:
            matched_feed_pairs = await self._notify_watchlist_matches(
                deal_id, updated_deal, discount
            )

        return {
            "deal_id": str(deal_id),
            "status": "evaluated",
            "is_high_value": is_high_value,
            "discount_percentage": float(discount),
            "estimated_value": float(result.estimated_price),
            "confidence": float(result.confidence),
            "matched_feed_pairs": matched_feed_pairs,
        }

    async def _notify_watchlist_matches(
        self,
        deal_id: UUID,
        deal: Deal,
        discount: Decimal,
    ) -> list[dict]:
        """Enqueue notifications for users whose watchlist feeds match this deal.

        Scans all active users' ``notification_preferences.saved_feeds`` for
        entries whose ``query`` keywords appear in the deal title AND whose
        ``min_discount`` threshold is met.  All matching ``{user_id, feed_id,
        feed_name}`` pairs are recorded; a single deal-notification SQS message
        is enqueued if at least one user matched.  The full list of matched pairs
        is returned so ``PipelineSummaryAgent`` can identify which feeds produced
        a result this run.

        Args:
            deal_id: UUID of the evaluated deal.
            deal: Evaluated Deal instance.
            discount: Calculated discount percentage.

        Returns:
            List of dicts with ``user_id``, ``feed_id``, and ``feed_name`` for
            every (user, feed) pair that matched this deal.
        """
        if not self.config.notification_queue_url:
            return []

        try:
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                users = await user_repo.find_active_users()
        except Exception as exc:
            logger.warning(f"Watchlist match: failed to load users: {exc}")
            return []

        deal_title_lower = deal.title.lower()
        matched_feed_pairs: list[dict] = []
        notified_user_ids: set[str] = set()

        for user in users:
            prefs = user.notification_preferences or {}
            saved_feeds: list[dict] = prefs.get("saved_feeds", []) or []
            for feed in saved_feeds:
                query_str = feed.get("query", "").strip().lower()
                min_discount = float(feed.get("min_discount", 0))
                if not query_str:
                    continue
                keywords = [w for w in query_str.split() if len(w) > 2][:3]
                if any(kw in deal_title_lower for kw in keywords):
                    if float(discount) >= min_discount:
                        matched_feed_pairs.append({
                            "user_id": str(user.id),
                            "feed_id": feed.get("id", ""),
                            "feed_name": feed.get("query", ""),
                        })
                        notified_user_ids.add(str(user.id))
                        # Continue to collect all matching feeds for this user

        if not notified_user_ids:
            return []

        logger.info(
            f"Watchlist match: deal {deal_id} matched {len(notified_user_ids)} user(s), "
            f"{len(matched_feed_pairs)} feed pair(s) — enqueuing"
        )

        loop = asyncio.get_running_loop()
        sqs = boto3.client("sqs", region_name=self.config.bedrock_region)
        message_body = json.dumps({"deal_id": str(deal_id)})
        try:
            await loop.run_in_executor(
                None,
                lambda: sqs.send_message(
                    QueueUrl=self.config.notification_queue_url,
                    MessageBody=message_body,
                ),
            )
        except Exception as exc:
            logger.error(f"Watchlist match: failed to enqueue notification for deal {deal_id}: {exc}")

        return matched_feed_pairs

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
