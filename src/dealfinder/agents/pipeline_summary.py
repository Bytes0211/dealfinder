"""PipelineSummaryAgent Lambda function for post-pipeline result checking.

After the Step Functions ``ProcessDeals`` Map state completes, this Lambda
inspects the ``evaluated_deals`` array.  If no deal is high-value — including
the case where the scanner found zero new deals — it publishes a ``no_deals``
event to the notification dispatch SQS queue.

A 24-hour rolling DynamoDB dedup key (``"no-deals-notif"``) prevents the
notification from being sent more than once per quiet window.  The 24-hour
clock starts from when the first notification fires, not at midnight.
"""

import asyncio
import json
import logging
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from dealfinder.agents.config import AgentConfig

logger = logging.getLogger(__name__)

_DEDUP_KEY = "no-deals-notif"
_DEDUP_TTL_SECONDS = 86_400  # 24 hours — rolling from first notification


class PipelineSummaryAgent:
    """Checks pipeline results and notifies users when no high-value deals were found.

    Receives the full Step Functions context after the ``ProcessDeals`` Map
    state and checks whether any evaluated deal has ``is_high_value=True``.
    Both cases — zero new deals discovered and deals evaluated but none
    high-value — are handled by the same ``any()`` check on the results array.

    A DynamoDB conditional write acts as a rolling 24-hour debounce so users
    receive at most one "no deals found" notification per quiet window.

    Example:
        agent = PipelineSummaryAgent()
        result = asyncio.run(agent.run(sfn_event))
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        """Initialise the pipeline summary agent.

        Args:
            config: Agent configuration. Loaded from environment if not provided.
        """
        self.config = config or AgentConfig()
        self._dynamodb: Any = None
        self._sqs: Any = None

    @property
    def dynamodb(self) -> Any:
        """Lazily initialise the DynamoDB resource."""
        if self._dynamodb is None:
            self._dynamodb = boto3.resource(
                "dynamodb", region_name=self.config.bedrock_region
            )
        return self._dynamodb

    @property
    def sqs(self) -> Any:
        """Lazily initialise the SQS client."""
        if self._sqs is None:
            self._sqs = boto3.client("sqs", region_name=self.config.bedrock_region)
        return self._sqs

    def _should_notify(self) -> bool:
        """Attempt to write the dedup key; return True if notification should be sent.

        Uses a conditional DynamoDB ``put_item`` so the check-and-set is atomic.
        If the key already exists within the 24-hour window the notification is
        suppressed.  Fails open: if DynamoDB is unavailable the notification is sent.

        Returns:
            True if the dedup key was absent (first notification this window).
            False if the key already exists (within the 24-hour window).
        """
        if not self.config.dedup_table_name:
            return True  # no dedup table configured — always notify

        try:
            table = self.dynamodb.Table(self.config.dedup_table_name)
            expires_at = int(time.time()) + _DEDUP_TTL_SECONDS
            table.put_item(
                Item={"pk": _DEDUP_KEY, "expires_at": expires_at},
                ConditionExpression="attribute_not_exists(pk)",
            )
            return True  # write succeeded — first notification this window
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info(
                    "No-deals dedup: notification suppressed within 24-hour window"
                )
                return False
            logger.warning(
                f"DynamoDB dedup check failed: {e} — proceeding with notification"
            )
            return True  # fail open

    def _enqueue_no_deals(self, timestamp: str, sources_scanned: int) -> None:
        """Publish a ``no_deals`` event to the notification dispatch SQS queue.

        Args:
            timestamp: ISO-8601 scan timestamp from the scanner (``scanned_at``).
            sources_scanned: Number of RSS sources scanned this pipeline run.
        """
        if not self.config.notification_queue_url:
            logger.warning(
                "No notification_queue_url configured — cannot enqueue no_deals message"
            )
            return

        message = json.dumps({
            "event_type": "no_deals",
            "timestamp": timestamp,
            "sources_scanned": sources_scanned,
        })
        self.sqs.send_message(
            QueueUrl=self.config.notification_queue_url,
            MessageBody=message,
        )
        logger.info(f"Enqueued no_deals notification for timestamp {timestamp}")

    async def run(self, event: dict) -> dict:
        """Check pipeline results and conditionally enqueue a no-deals notification.

        If at least one evaluated deal has ``is_high_value=True``, no action is
        taken.  Otherwise the 24-hour dedup key is checked; if absent, a
        ``no_deals`` SQS message is published for the Messenger Agent to deliver.

        Args:
            event: Step Functions context containing ``evaluated_deals`` list,
                ``scanned_at`` ISO-8601 timestamp, and ``sources_scanned`` count.

        Returns:
            The input event unchanged (Step Functions ``ResultPath=null``).
        """
        evaluated_deals: list[dict] = event.get("evaluated_deals", [])
        scanned_at: str = event.get("scanned_at", "")
        sources_scanned: int = event.get("sources_scanned", 0)

        has_high_value = any(d.get("is_high_value") for d in evaluated_deals)

        if has_high_value:
            high_value_count = sum(1 for d in evaluated_deals if d.get("is_high_value"))
            logger.info(
                f"Pipeline had {high_value_count} high-value deal(s) — no notification needed"
            )
            return event

        logger.info(
            f"No high-value deals found (evaluated {len(evaluated_deals)}, "
            f"scanned {sources_scanned} sources) — checking dedup"
        )

        loop = asyncio.get_running_loop()
        should_notify = await loop.run_in_executor(None, self._should_notify)

        if should_notify:
            await loop.run_in_executor(
                None, lambda: self._enqueue_no_deals(scanned_at, sources_scanned)
            )

        return event


def handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point for the Pipeline Summary Agent.

    Args:
        event: Step Functions context with ``evaluated_deals``, ``scanned_at``,
            and ``sources_scanned`` fields.
        context: Lambda execution context (unused).

    Returns:
        The input event unchanged.
    """
    return asyncio.run(PipelineSummaryAgent().run(event))
