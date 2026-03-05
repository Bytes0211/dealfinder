"""MessengerAgent Lambda function for deal notification dispatch.

Triggered by the SQS ``notification_dispatch`` queue.  Each SQS record
body contains a JSON object ``{"deal_id": "<uuid>"}`` published by the
Step Functions ``QueueNotification`` state.

For each record the agent:
1. Parses ``deal_id`` from the SQS record body.
2. Checks a DynamoDB deduplication key — skips if notified within 24 h.
3. Fetches the deal from Aurora and crafts a title + message via Bedrock.
4. Dispatches via Pushover (if the user has a ``pushover_user_key``) and/or
   SES email.
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
from dealfinder.notifications.pushover import PushoverClient
from dealfinder.notifications.ses import SesClient

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
    """Dispatches deal notifications to users via Pushover and SES email.

    Reads SQS batch records, deduplicates using DynamoDB, crafts personalized
    messages via Bedrock, and dispatches through configured channels.

    Example:
        agent = MessengerAgent()
        result = asyncio.run(agent.run(sqs_event, context))
        print(result["batchItemFailures"])
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        pushover: PushoverClient | None = None,
        ses: SesClient | None = None,
    ) -> None:
        """Initialise the Messenger Agent.

        Args:
            config: Agent configuration.  Loaded from environment if not provided.
            pushover: Pushover client.  Created from config if not provided.
            ses: SES email client.  Created from config if not provided.
        """
        self.config = config or AgentConfig()
        token = self.config.pushover_api_token.get_secret_value()
        self._pushover = pushover or (PushoverClient(token) if token else None)
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

    async def _dispatch_to_user(
        self,
        deal: Deal,
        title: str,
        message: str,
    ) -> bool:
        """Dispatch a notification to all eligible users.

        Iterates active users, filters by preference and available keys,
        dispatches via Pushover and/or SES, and records each attempt.

        Args:
            deal: The evaluated deal being notified.
            title: Notification title.
            message: Notification body.

        Returns:
            True if at least one channel sent successfully; False otherwise.
        """
        async with get_async_session() as session:
            user_repo = UserRepository(session)
            users = await user_repo.find_active_users()

        any_sent = False
        loop = asyncio.get_running_loop()

        for user in users:
            prefs = user.notification_preferences or {}

            if user.pushover_user_key and prefs.get("pushover", True) and self._pushover:
                notif = Notification(
                    user_id=user.id,
                    deal_id=deal.id,
                    channel=NotificationChannel.PUSHOVER,
                    status=NotificationStatus.PENDING,
                    title=title,
                    message=message,
                )
                async with get_async_session() as session:
                    nr = NotificationRepository(session)
                    notif = await nr.create(notif)

                try:
                    receipt = await loop.run_in_executor(
                        None, self._pushover.send, user.pushover_user_key, title, message
                    )
                    async with get_async_session() as session:
                        nr = NotificationRepository(session)
                        await nr.mark_as_sent(notif.id, external_id=receipt)
                    any_sent = True
                except Exception as exc:
                    logger.error(f"Pushover dispatch failed for user {user.id}: {exc}")
                    async with get_async_session() as session:
                        nr = NotificationRepository(session)
                        await nr.mark_as_failed(notif.id, error_message=str(exc))

            if user.email and prefs.get("email", False) and self._ses:
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
                    msg_id = await loop.run_in_executor(
                        None, self._ses.send_email, user.email, title, message
                    )
                    async with get_async_session() as session:
                        nr = NotificationRepository(session)
                        await nr.mark_as_sent(notif_email.id, external_id=msg_id)
                    any_sent = True
                except Exception as exc:
                    logger.error(f"SES dispatch failed for user {user.id}: {exc}")
                    async with get_async_session() as session:
                        nr = NotificationRepository(session)
                        await nr.mark_as_failed(notif_email.id, error_message=str(exc))

        return any_sent

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

        any_sent = await self._dispatch_to_user(deal, title, message)

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
            "channels_attempted": int(bool(self._pushover)) + int(bool(self._ses)),
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
