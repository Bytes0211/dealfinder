"""PipelineSummaryAgent Lambda function for post-pipeline result checking.

After the Step Functions ``ProcessDeals`` Map state completes, this Lambda
aggregates ``matched_feed_pairs`` from all evaluated deals and enqueues a
per-feed ``no_deals_feed`` notification for every active user whose saved
feed did *not* produce a deal match this run.  A 24-hour rolling DynamoDB
dedup key per (user, feed) pair prevents repeat notifications within one
quiet window.
"""

import asyncio
import json
import logging
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from dealfinder.agents.config import AgentConfig
from dealfinder.data.repository import UserRepository
from dealfinder.db.connection import get_async_session

logger = logging.getLogger(__name__)

_DEDUP_TTL_SECONDS = 86_400  # 24 hours — rolling from first notification


class PipelineSummaryAgent:
    """Checks pipeline results and sends per-feed no-deals notifications.

    After the ``ProcessDeals`` Map state, aggregates ``matched_feed_pairs``
    from all evaluated deals.  For each active user whose saved feeds did
    *not* produce a match this run, a per-feed "still searching"
    notification is dispatched via SQS (subject to 24-hour dedup per
    (user, feed) pair).

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

    def _check_and_set_dedup(self, dedup_key: str) -> bool:
        """Attempt a conditional DynamoDB write for a per-feed dedup key.

        Uses a conditional ``put_item`` so the check-and-set is atomic.
        Returns True (notify) if the key was absent; False (suppress) if it
        already exists within the 24-hour window.  Fails open so users are
        notified when DynamoDB is unavailable.

        Args:
            dedup_key: DynamoDB partition key for this (user, feed) notification.

        Returns:
            True if the notification should be sent, False if suppressed.
        """
        if not self.config.dedup_table_name:
            return True  # no dedup table configured — always notify

        try:
            table = self.dynamodb.Table(self.config.dedup_table_name)
            expires_at = int(time.time()) + _DEDUP_TTL_SECONDS
            table.put_item(
                Item={"pk": dedup_key, "expires_at": expires_at},
                ConditionExpression="attribute_not_exists(pk)",
            )
            return True  # write succeeded — first notification this window
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.debug(
                    f"Dedup key {dedup_key!r} within 24h window — suppressed"
                )
                return False
            logger.warning(
                f"DynamoDB dedup check failed for {dedup_key!r}: {e} "
                "— proceeding with notification"
            )
            return True  # fail open

    def _enqueue_no_deals_feed(
        self,
        user_id: str,
        feed_id: str,
        feed_name: str,
        timestamp: str,
    ) -> None:
        """Publish a ``no_deals_feed`` event to the notification dispatch SQS queue.

        Args:
            user_id: String UUID of the user to notify.
            feed_id: Saved-feed entry identifier.
            feed_name: Human-readable feed label (the saved feed query string).
            timestamp: ISO-8601 scan timestamp from the scanner.
        """
        if not self.config.notification_queue_url:
            logger.warning(
                "No notification_queue_url configured — cannot enqueue no_deals_feed message"
            )
            return

        message = json.dumps({
            "event_type": "no_deals_feed",
            "user_id": user_id,
            "feed_id": feed_id,
            "feed_name": feed_name,
            "timestamp": timestamp,
        })
        self.sqs.send_message(
            QueueUrl=self.config.notification_queue_url,
            MessageBody=message,
        )
        logger.info(
            f"Enqueued no_deals_feed notification for user {user_id}, feed '{feed_name}'"
        )

    async def _check_unmatched_feeds(
        self,
        matched_pairs: list[dict],
        scanned_at: str,
    ) -> None:
        """Enqueue per-feed no-deals notifications for unmatched user feeds.

        Loads all active users, builds the set of ``(user_id, feed_id)`` pairs
        that produced at least one deal match this pipeline run, then for each
        unmatched ``(user_id, feed_id)`` pair checks a rolling 24-hour dedup
        key and, if absent, enqueues a ``no_deals_feed`` SQS message.

        Args:
            matched_pairs: List of ``{user_id, feed_id, feed_name}`` dicts
                collected from all evaluated deals this run.
            scanned_at: ISO-8601 scan timestamp.
        """
        if not self.config.notification_queue_url:
            return

        try:
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                users = await user_repo.find_active_users()
        except Exception as exc:
            logger.warning(f"_check_unmatched_feeds: failed to load users: {exc}")
            return

        matched_set: set[tuple[str, str]] = {
            (p["user_id"], p["feed_id"]) for p in matched_pairs
        }
        loop = asyncio.get_running_loop()

        for user in users:
            prefs = user.notification_preferences or {}
            saved_feeds: list[dict] = prefs.get("saved_feeds", []) or []
            for feed in saved_feeds:
                feed_id = feed.get("id", "")
                feed_name = feed.get("query", "")
                if not feed_id:
                    continue

                user_id = str(user.id)
                if (user_id, feed_id) in matched_set:
                    continue  # this feed produced a deal this run

                dedup_key = f"no-deals-feed#{user_id}#{feed_id}"
                # Capture loop variables to avoid late-binding in lambdas
                _key = dedup_key
                _uid, _fid, _fn, _ts = user_id, feed_id, feed_name, scanned_at
                should_notify = await loop.run_in_executor(
                    None, lambda k=_key: self._check_and_set_dedup(k)
                )
                if should_notify:
                    await loop.run_in_executor(
                        None,
                        lambda uid=_uid, fid=_fid, fn=_fn, ts=_ts: (
                            self._enqueue_no_deals_feed(
                                user_id=uid,
                                feed_id=fid,
                                feed_name=fn,
                                timestamp=ts,
                            )
                        ),
                    )

    async def run(self, event: dict) -> dict:
        """Check pipeline results and enqueue per-feed no-deals notifications.

        Aggregates ``matched_feed_pairs`` from all evaluated deals then calls
        ``_check_unmatched_feeds`` to dispatch "still searching" messages for
        any ``(user, feed)`` pair that did not produce a deal match this run.

        Args:
            event: Step Functions context containing ``evaluated_deals`` list
                and ``scanned_at`` ISO-8601 timestamp.

        Returns:
            The input event unchanged (Step Functions ``ResultPath=null``).
        """
        evaluated_deals: list[dict] = event.get("evaluated_deals", [])
        scanned_at: str = event.get("scanned_at", "")

        matched_pairs: list[dict] = []
        for deal in evaluated_deals:
            matched_pairs.extend(deal.get("matched_feed_pairs", []))

        high_value_count = sum(1 for d in evaluated_deals if d.get("is_high_value"))
        logger.info(
            f"Pipeline summary: {high_value_count} high-value deal(s) across "
            f"{len(evaluated_deals)} evaluated, {len(matched_pairs)} matched feed pair(s)"
        )

        await self._check_unmatched_feeds(matched_pairs, scanned_at)
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
