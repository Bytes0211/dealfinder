"""Unit tests for MessengerAgent.

Uses mocked DynamoDB, database sessions, Pushover, and SES clients so
no AWS services or real databases are required.
"""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from dealfinder.agents.config import AgentConfig
from dealfinder.agents.messenger import (
    MessengerAgent,
    _build_notification_prompt,
    _parse_notification_text,
)
from dealfinder.db.models import Deal, DealSource, DealStatus


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def _make_deal(
    title: str = "Test Deal",
    url: str = "https://example.com/deal",
    sale_price: float = 50.0,
    estimated_value: float = 100.0,
    discount_percentage: float = 50.0,
    brand: str = "TestBrand",
    category: str = "electronics",
) -> Deal:
    """Create an in-memory Deal for testing."""
    source = DealSource(name="Test Feed", url="https://example.com/feed.rss")
    deal = Deal(
        id=uuid4(),
        source=source,
        source_id=uuid4(),
        external_id="ext-001",
        title=title,
        url=url,
        sale_price=Decimal(str(sale_price)),
        original_price=Decimal(str(sale_price * 2)),
        estimated_value=Decimal(str(estimated_value)),
        discount_percentage=Decimal(str(discount_percentage)),
        is_high_value=True,
        brand=brand,
        category=category,
        status=DealStatus.EVALUATED,
    )
    return deal


def _make_config(**kwargs) -> AgentConfig:
    """Create a minimal AgentConfig for tests."""
    defaults = dict(
        discount_threshold=20.0,
        bedrock_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        notification_queue_url="",
        pushover_api_token="",
        ses_sender_email="",
        dedup_table_name="",
    )
    defaults.update(kwargs)
    return AgentConfig(**defaults)


# ─────────────────────────────────────────────
# Prompt / parse helpers
# ─────────────────────────────────────────────


class TestBuildNotificationPrompt:
    """Tests for _build_notification_prompt."""

    def test_prompt_contains_deal_fields(self) -> None:
        """The prompt should include title, price, discount, and URL."""
        deal = _make_deal(title="Laptop X", url="https://ex.com/l", sale_price=400, discount_percentage=40)
        prompt = _build_notification_prompt(deal)

        assert "Laptop X" in prompt
        assert "40%" in prompt
        assert "https://ex.com/l" in prompt

    def test_prompt_includes_brand_when_present(self) -> None:
        """Brand should appear in the prompt if set on the deal."""
        deal = _make_deal(brand="Acme")
        assert "Acme" in _build_notification_prompt(deal)

    def test_prompt_omits_brand_when_absent(self) -> None:
        """Brand line should not appear if deal.brand is None."""
        deal = _make_deal()
        deal.brand = None
        assert "Brand:" not in _build_notification_prompt(deal)


class TestParseNotificationText:
    """Tests for _parse_notification_text."""

    def test_parses_valid_json(self) -> None:
        """Valid JSON with title and message should be returned as-is."""
        text = '{"title": "Great Deal", "message": "50% off laptops"}'
        title, message = _parse_notification_text(text)
        assert title == "Great Deal"
        assert message == "50% off laptops"

    def test_parses_json_embedded_in_text(self) -> None:
        """JSON embedded in prose should be extracted correctly."""
        text = 'Here is your notification: {"title": "Alert", "message": "Buy now"} — enjoy!'
        title, message = _parse_notification_text(text)
        assert title == "Alert"
        assert message == "Buy now"

    def test_falls_back_on_invalid_json(self) -> None:
        """Unparseable text should fall back to generic title."""
        title, message = _parse_notification_text("not json at all")
        assert title == "🔥 Deal Alert"
        assert "not json at all" in message

    def test_falls_back_when_title_or_message_missing(self) -> None:
        """JSON missing either title or message should trigger fallback."""
        title, message = _parse_notification_text('{"title": "Only title"}')
        assert title == "🔥 Deal Alert"


# ─────────────────────────────────────────────
# MessengerAgent._is_duplicate
# ─────────────────────────────────────────────


class TestMessengerAgentIsDuplicate:
    """Tests for MessengerAgent._is_duplicate."""

    def test_returns_false_when_no_dedup_table(self) -> None:
        """With no dedup_table_name configured the check always returns False."""
        config = _make_config(dedup_table_name="")
        agent = MessengerAgent(config=config)
        assert agent._is_duplicate(uuid4()) is False

    def test_returns_false_on_first_write(self) -> None:
        """A successful conditional write means no duplicate — return False."""
        config = _make_config(dedup_table_name="my-dedup-table")
        agent = MessengerAgent(config=config)

        mock_table = MagicMock()
        mock_table.put_item.return_value = {}  # success

        with patch.object(type(agent), "dynamodb", new_callable=lambda: property(lambda self: MagicMock(Table=lambda name: mock_table))):
            result = agent._is_duplicate(uuid4())

        assert result is False

    def test_returns_true_on_conditional_check_failure(self) -> None:
        """ConditionalCheckFailedException means already notified — return True."""
        config = _make_config(dedup_table_name="my-dedup-table")
        agent = MessengerAgent(config=config)

        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
            "PutItem",
        )

        with patch.object(type(agent), "dynamodb", new_callable=lambda: property(lambda self: MagicMock(Table=lambda name: mock_table))):
            result = agent._is_duplicate(uuid4())

        assert result is True

    def test_fails_open_on_unexpected_dynamodb_error(self) -> None:
        """Unexpected DynamoDB errors should fail open (return False)."""
        config = _make_config(dedup_table_name="my-dedup-table")
        agent = MessengerAgent(config=config)

        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": ""}},
            "PutItem",
        )

        with patch.object(type(agent), "dynamodb", new_callable=lambda: property(lambda self: MagicMock(Table=lambda name: mock_table))):
            result = agent._is_duplicate(uuid4())

        assert result is False


# ─────────────────────────────────────────────
# MessengerAgent.notify_deal
# ─────────────────────────────────────────────


class TestMessengerAgentNotifyDeal:
    """Tests for MessengerAgent.notify_deal."""

    async def test_returns_skipped_for_duplicate(self) -> None:
        """A deal that has already been notified should be skipped."""
        config = _make_config()
        agent = MessengerAgent(config=config)

        with patch.object(agent, "_is_duplicate", return_value=True):
            result = await agent.notify_deal(uuid4())

        assert result["status"] == "skipped"
        assert result["reason"] == "duplicate within 24h"

    async def test_returns_not_found_for_missing_deal(self) -> None:
        """A deal_id that doesn't exist in the DB should return not_found."""
        config = _make_config()
        agent = MessengerAgent(config=config)

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(agent, "_is_duplicate", return_value=False),
            patch("dealfinder.agents.messenger.get_async_session", return_value=mock_session),
            patch("dealfinder.agents.messenger.DealRepository", return_value=mock_repo),
        ):
            result = await agent.notify_deal(uuid4())

        assert result["status"] == "not_found"

    async def test_notified_deal_marks_status_notified(self) -> None:
        """A successfully processed deal should be marked NOTIFIED in the DB."""
        config = _make_config()
        deal = _make_deal()

        mock_deal_repo = AsyncMock()
        mock_deal_repo.get_by_id.return_value = deal
        mock_deal_repo.update_status = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        agent = MessengerAgent(config=config)
        with (
            patch.object(agent, "_is_duplicate", return_value=False),
            patch.object(agent, "_craft_message", return_value=("Title", "Message")),
            patch.object(agent, "_dispatch_to_user", new_callable=AsyncMock, return_value=True),
            patch("dealfinder.agents.messenger.get_async_session", return_value=mock_session),
            patch("dealfinder.agents.messenger.DealRepository", return_value=mock_deal_repo),
        ):
            result = await agent.notify_deal(deal.id)

        assert result["status"] == "notified"
        mock_deal_repo.update_status.assert_called_once_with(deal.id, DealStatus.NOTIFIED)

    async def test_raises_when_all_channels_fail(self) -> None:
        """If _dispatch_to_user returns False, a RuntimeError should be raised for SQS retry."""
        config = _make_config()
        deal = _make_deal()

        mock_deal_repo = AsyncMock()
        mock_deal_repo.get_by_id.return_value = deal

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        agent = MessengerAgent(config=config)
        with (
            patch.object(agent, "_is_duplicate", return_value=False),
            patch.object(agent, "_craft_message", return_value=("Title", "Message")),
            patch.object(agent, "_dispatch_to_user", new_callable=AsyncMock, return_value=False),
            patch("dealfinder.agents.messenger.get_async_session", return_value=mock_session),
            patch("dealfinder.agents.messenger.DealRepository", return_value=mock_deal_repo),
        ):
            with pytest.raises(RuntimeError, match="All notification channels failed"):
                await agent.notify_deal(deal.id)

        mock_deal_repo.update_status.assert_not_called()


# ─────────────────────────────────────────────
# MessengerAgent.run (SQS handler)
# ─────────────────────────────────────────────


class TestMessengerAgentRun:
    """Tests for MessengerAgent.run (SQS batch handler)."""

    async def test_processes_valid_sqs_records(self) -> None:
        """Valid SQS records should be processed without failures."""
        deal_id = str(uuid4())
        event = {
            "Records": [
                {"messageId": "msg-1", "body": json.dumps({"deal_id": deal_id})}
            ]
        }

        config = _make_config()
        agent = MessengerAgent(config=config)

        with patch.object(agent, "notify_deal", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = {"status": "notified", "deal_id": deal_id}
            result = await agent.run(event, context=None)

        assert result["batchItemFailures"] == []
        mock_notify.assert_awaited_once()

    async def test_malformed_sqs_body_added_to_failures(self) -> None:
        """SQS records with malformed JSON body should be added to batchItemFailures."""
        event = {
            "Records": [
                {"messageId": "msg-bad", "body": "{not valid json}"}
            ]
        }
        config = _make_config()
        agent = MessengerAgent(config=config)
        result = await agent.run(event, context=None)

        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-bad"

    async def test_missing_deal_id_added_to_failures(self) -> None:
        """SQS records missing deal_id key should be added to batchItemFailures."""
        event = {
            "Records": [
                {"messageId": "msg-no-id", "body": json.dumps({"other": "field"})}
            ]
        }
        config = _make_config()
        agent = MessengerAgent(config=config)
        result = await agent.run(event, context=None)

        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-no-id"

    async def test_notify_deal_exception_adds_to_failures(self) -> None:
        """If notify_deal raises, the message ID should appear in batchItemFailures."""
        deal_id = str(uuid4())
        event = {
            "Records": [
                {"messageId": "msg-err", "body": json.dumps({"deal_id": deal_id})}
            ]
        }
        config = _make_config()
        agent = MessengerAgent(config=config)

        with patch.object(agent, "notify_deal", new_callable=AsyncMock) as mock_notify:
            mock_notify.side_effect = RuntimeError("DB connection failed")
            result = await agent.run(event, context=None)

        assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-err"

    async def test_partial_batch_failure(self) -> None:
        """Only failed records should appear in batchItemFailures for a mixed batch."""
        good_id = str(uuid4())
        bad_id = str(uuid4())
        event = {
            "Records": [
                {"messageId": "good", "body": json.dumps({"deal_id": good_id})},
                {"messageId": "bad", "body": json.dumps({"deal_id": bad_id})},
            ]
        }
        config = _make_config()
        agent = MessengerAgent(config=config)

        async def _mock_notify(deal_id):
            if str(deal_id) == bad_id:
                raise RuntimeError("fail")
            return {"status": "notified"}

        with patch.object(agent, "notify_deal", side_effect=_mock_notify):
            result = await agent.run(event, context=None)

        assert len(result["batchItemFailures"]) == 1
        assert result["batchItemFailures"][0]["itemIdentifier"] == "bad"
