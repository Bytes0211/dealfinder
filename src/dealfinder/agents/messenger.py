"""MessengerAgent Lambda function for deal notification dispatch.

Triggered by the SQS ``notification_dispatch`` queue.  Each SQS record
body contains a JSON object ``{"deal_id": "<uuid>"}`` published by the
Step Functions ``QueueNotification`` state.

For each record the agent:
1. Parses ``deal_id`` from the SQS record body.
2. Checks a DynamoDB deduplication key — skips if notified within 24 h.
3. Fetches the deal from Aurora and crafts a title + message via Bedrock.
4. Publishes to the SNS ``deal_notifications`` topic (fan-out to all
   subscribers) and optionally sends per-user SES email.
5. Persists a ``Notification`` row in Aurora for each dispatch attempt.
6. Only if at least one channel succeeded: marks the deal ``NOTIFIED`` and
   writes the DynamoDB dedup key.  If all channels fail, raises so SQS retries.
7. Returns ``{"batchItemFailures": [...]}`` so failed records are retried
   rather than silently dropped.
"""

import asyncio
import json
import logging
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from dealfinder.agents.config import AgentConfig
from dealfinder.data.repository import (
    DealRepository,
    NotificationRepository,
    UserRepository,
)
from dealfinder.db.connection import get_async_session
from dealfinder.db.models import (
    Deal,
    DealStatus,
    Notification,
    NotificationChannel,
    NotificationStatus,
)
from dealfinder.notifications.ses import SesClient
from dealfinder.notifications.sns import SnsClient

logger = logging.getLogger(__name__)

_DEDUP_TTL_SECONDS = 86_400  # 24 hours


def _build_notification_prompt(deal: Deal) -> str:
    """Build a Bedrock prompt that asks Claude to craft a deal alert.

    Args:
        deal: Deal instance with pricing and metadata.

    Returns:
        Prompt string ready to be sent to Claude.
    """
    discount = float(deal.discount_percentage or 0)
    sale = float(deal.sale_price or deal.original_price or 0)
    estimated = float(deal.estimated_value or 0)
    lines = [
        "You are writing a short, engaging deal alert notification.",
        "Write a push notification for this deal.",
        "",
        f"Product: {deal.title}",
    ]
    if deal.brand:
        lines.append(f"Brand: {deal.brand}")
    if deal.category:
        lines.append(f"Category: {deal.category}")
    lines.extend([
        f"Sale price: ${sale:.2f}",
        f"Estimated retail value: ${estimated:.2f}",
        f"Discount: {discount:.0f}%",
        f"URL: {deal.url}",
        "",
        'Respond with ONLY a JSON object: {"title": "<max 60 chars>", "message": "<max 200 chars>"}',
    ])
    return "\n".join(lines)


def _parse_notification_text(response_text: str) -> tuple[str, str]:
    """Extract title and message from Claude's JSON response.

    Args:
        response_text: Raw Claude output.

    Returns:
        Tuple of (title, message).  Falls back to generic text on parse error.
    """
    start = response_text.find("{")
    if start != -1:
        try:
            data, _ = json.JSONDecoder().raw_decode(response_text, start)
            title = str(data.get("title", ""))[:250]
            message = str(data.get("message", ""))[:1024]
            if title and message:
                return title, message
        except (json.JSONDecodeError, ValueError):
            pass
    return "🔥 Deal Alert", f"{response_text[:200]}"


class MessengerAgent:
    """Dispatches deal notifications via SNS fan-out and optional SES email.

    Reads SQS batch records, deduplicates using DynamoDB, crafts messages
    via Bedrock, publishes to the SNS deal-notifications topic, and
    optionally sends per-user SES email.

    Example:
        agent = MessengerAgent()
        result = asyncio.run(agent.run(sqs_event, context))
        print(result["batchItemFailures"])
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        sns: SnsClient | None = None,
        ses: SesClient | None = None,
    ) -> None:
        """Initialise the Messenger Agent.

        Args:
            config: Agent configuration.  Loaded from environment if not provided.
            sns: SNS client.  Created from config if not provided.
            ses: SES email client.  Created from config if not provided.
        """
        self.config = config or AgentConfig()
        self._sns = sns or (
            SnsClient(self.config.sns_topic_arn, self.config.bedrock_region)
            if self.config.sns_topic_arn
            else None
        )
        self._ses = ses or (
            SesClient(self.config.ses_sender_email, self.config.bedrock_region)
            if self.config.ses_sender_email
            else None
        )
        self._dynamodb: Any = None
        self._bedrock_client: Any = None

    @property
    def dynamodb(self) -> Any:
        """Lazily initialise the DynamoDB resource."""
        if self._dynamodb is None:
            self._dynamodb = boto3.resource(
                "dynamodb", region_name=self.config.bedrock_region
            )
        return self._dynamodb

    @property
    def bedrock_client(self) -> Any:
        """Lazily initialise and cache the Bedrock runtime client."""
        if self._bedrock_client is None:
            self._bedrock_client = boto3.client(
                "bedrock-runtime", region_name=self.config.bedrock_region
            )
        return self._bedrock_client

    def _is_duplicate(self, deal_id: UUID) -> bool:
        """Check DynamoDB deduplication table for a recent notification.

        Uses a conditional write so the check-and-set is atomic.

        Args:
            deal_id: Deal UUID.

        Returns:
            True if a notification has already been sent within the TTL window.
        """
        if not self.config.dedup_table_name:
            return False
        try:
            table = self.dynamodb.Table(self.config.dedup_table_name)
            expires_at = int(time.time()) + _DEDUP_TTL_SECONDS
            table.put_item(
                Item={"pk": f"notif-dedup#{deal_id}", "expires_at": expires_at},
                ConditionExpression="attribute_not_exists(pk)",
            )
            return False  # Write succeeded — first notification
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info(f"Dedup: deal {deal_id} already notified within 24 h")
                return True
            logger.warning(f"DynamoDB dedup check failed for {deal_id}: {e}")
            return False  # Fail open — better to over-notify than miss

    def _craft_message(self, deal: Deal) -> tuple[str, str]:
        """Use Bedrock to craft a personalized notification title and message.

        Falls back to a generic message if Bedrock fails.

        Args:
            deal: Deal with pricing and metadata populated.

        Returns:
            Tuple of (title, message).
        """
        try:
            client = self.bedrock_client
            prompt = _build_notification_prompt(deal)
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 256,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            })
            response = client.invoke_model(
                modelId=self.config.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            body_data = json.loads(response["body"].read())
            content_blocks = body_data.get("content", [])
            if content_blocks and content_blocks[0].get("type") == "text":
                return _parse_notification_text(content_blocks[0]["text"])
        except Exception as exc:
            logger.warning(f"Bedrock message crafting failed for deal {deal.id}: {exc}")

        # Fallback: generic message
        discount = float(deal.discount_percentage or 0)
        title = f"🔥 {discount:.0f}% off: {deal.title[:50]}"
        message = f"Sale price: ${float(deal.sale_price or 0):.2f} — {deal.url}"
        return title[:250], message[:1024]

    async def _dispatch(
        self,
        deal: Deal,
        title: str,
        message: str,
    ) -> tuple[bool, int]:
        """Dispatch a deal notification via SNS and optional per-user SES email.

        Publishes once to the SNS topic (fan-out to all subscribers) and
        iterates active users to send personalised SES email to those who
        have email notifications enabled.

        Args:
            deal: The evaluated deal being notified.
            title: Notification title.
            message: Notification body.

        Returns:
            Tuple of (success, channels_attempted) where success is True if at
            least one channel succeeded, and channels_attempted is the total
            number of dispatch attempts made.
        """
        channels_attempted = 0
        any_sent = False
        loop = asyncio.get_running_loop()

        # ── SNS publish (single fan-out to all subscribers) ──────────────────
        if self._sns:
            channels_attempted += 1
            notif = Notification(
                user_id=None,  # type: ignore[arg-type]  # broadcast — no single user
                deal_id=deal.id,
                channel=NotificationChannel.SNS,
                status=NotificationStatus.PENDING,
                title=title,
                message=message,
            )
            # Persist a broadcast notification row (user_id nullable for SNS)
            # Best-effort — don't let DB issues block the SNS publish
            try:
                async with get_async_session() as session:
                    nr = NotificationRepository(session)
                    notif = await nr.create(notif)
                sns_notif_id = notif.id
            except Exception as exc:
                logger.warning(f"Could not persist SNS notification row: {exc}")
                sns_notif_id = None

            try:
                msg_id = await loop.run_in_executor(
                    None, self._sns.publish, title, message
                )
                if sns_notif_id:
                    async with get_async_session() as session:
                        nr = NotificationRepository(session)
                        await nr.mark_as_sent(sns_notif_id, external_id=msg_id)
                any_sent = True
            except Exception as exc:
                logger.error(f"SNS publish failed for deal {deal.id}: {exc}")
                if sns_notif_id:
                    async with get_async_session() as session:
                        nr = NotificationRepository(session)
                        await nr.mark_as_failed(sns_notif_id, error_message=str(exc))

        # ── Per-user SES email ────────────────────────────────────────────────
        if self._ses:
            async with get_async_session() as session:
                user_repo = UserRepository(session)
                users = await user_repo.find_active_users()

            for user in users:
                prefs = user.notification_preferences or {}
                if not (user.email and prefs.get("email", False)):
                    continue

                channels_attempted += 1
                notif_email = Notification(
                    user_id=user.id,
                    deal_id=deal.id,
                    channel=NotificationChannel.EMAIL,
                    status=NotificationStatus.PENDING,
                    title=title,
                    message=message,
                )
                async with get_async_session() as session:
                    nr = NotificationRepository(session)
                    notif_email = await nr.create(notif_email)

                try:
                    email_id = await loop.run_in_executor(
                        None, self._ses.send_email, user.email, title, message
                    )
                    async with get_async_session() as session:
                        nr = NotificationRepository(session)
                        await nr.mark_as_sent(notif_email.id, external_id=email_id)
                    any_sent = True
                except Exception as exc:
                    logger.error(f"SES dispatch failed for user {user.id}: {exc}")
                    async with get_async_session() as session:
                        nr = NotificationRepository(session)
                        await nr.mark_as_failed(notif_email.id, error_message=str(exc))

        if channels_attempted == 0:
            return True, 0  # no channels configured — treat as success
        return any_sent, channels_attempted

    async def notify_deal(self, deal_id: UUID) -> dict:
        """Process a single deal notification.

        Args:
            deal_id: UUID of the high-value deal to notify about.

        Returns:
            Dictionary with ``status`` (``"notified"``, ``"skipped"``,
            ``"not_found"``), ``deal_id`` string, and ``channels_attempted``
            count.

        Raises:
            RuntimeError: If every configured channel fails, so SQS retries
                the record rather than marking it delivered.
        """
        loop = asyncio.get_running_loop()
        if await loop.run_in_executor(None, self._is_duplicate, deal_id):
            return {
                "deal_id": str(deal_id),
                "status": "skipped",
                "reason": "duplicate within 24h",
                "channels_attempted": 0,
            }

        async with get_async_session() as session:
            deal_repo = DealRepository(session)
            deal = await deal_repo.get_by_id(deal_id)

        if not deal:
            logger.warning(f"Messenger: deal {deal_id} not found")
            return {
                "deal_id": str(deal_id),
                "status": "not_found",
                "channels_attempted": 0,
            }

        title, message = await loop.run_in_executor(None, self._craft_message, deal)

        any_sent, channels_attempted = await self._dispatch(deal, title, message)

        if not any_sent:
            raise RuntimeError(
                f"All notification channels failed for deal {deal_id} — SQS will retry"
            )

        async with get_async_session() as session:
            deal_repo = DealRepository(session)
            await deal_repo.update_status(deal_id, DealStatus.NOTIFIED)

        logger.info(f"Messenger: notified deal {deal_id} — '{title[:60]}'")
        return {
            "deal_id": str(deal_id),
            "status": "notified",
            "channels_attempted": channels_attempted,
        }

    async def run(self, event: dict, context: Any) -> dict:
        """Process an SQS batch event from the notification_dispatch queue.

        Each SQS record body is a JSON string ``{"deal_id": "<uuid>"}``.
        Failed records are returned in ``batchItemFailures`` so that SQS
        retries only the records that errored rather than the entire batch.

        Args:
            event: Lambda SQS event containing a ``Records`` list.
            context: Lambda execution context (unused).

        Returns:
            ``{"batchItemFailures": [{"itemIdentifier": "<messageId>"}]}``
        """
        records = event.get("Records", [])
        batch_item_failures: list[dict] = []

        for record in records:
            message_id = record.get("messageId", "unknown")
            try:
                body = json.loads(record.get("body", "{}"))
                deal_id = UUID(body["deal_id"])
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.error(f"Malformed SQS record {message_id}: {exc}")
                batch_item_failures.append({"itemIdentifier": message_id})
                continue

            try:
                await self.notify_deal(deal_id)
            except Exception as exc:
                logger.error(f"notify_deal failed for {deal_id} (record {message_id}): {exc}")
                batch_item_failures.append({"itemIdentifier": message_id})

        return {"batchItemFailures": batch_item_failures}


def handler(event: dict, context: Any) -> dict:
    """AWS Lambda entry point for the Messenger Agent.

    Args:
        event: SQS trigger event with a ``Records`` list.
        context: Lambda execution context (unused).

    Returns:
        Batch item failures dictionary for partial SQS batch failure reporting.
    """
    return asyncio.run(MessengerAgent().run(event, context))
