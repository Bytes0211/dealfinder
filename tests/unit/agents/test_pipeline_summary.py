"""Unit tests for PipelineSummaryAgent.

Uses mocked DynamoDB and SQS clients so no AWS services are required.
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from dealfinder.agents.config import AgentConfig
from dealfinder.agents.pipeline_summary import PipelineSummaryAgent


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def _make_config(**kwargs) -> AgentConfig:
    """Create a minimal AgentConfig for pipeline summary tests."""
    defaults = dict(
        bedrock_region="us-east-1",
        notification_queue_url="https://sqs.us-east-1.amazonaws.com/123/test-queue",
        dedup_table_name="test-pipeline-dedup",
    )
    defaults.update(kwargs)
    return AgentConfig(**defaults)


def _make_event(
    evaluated_deals: list | None = None,
    scanned_at: str = "2026-03-06T17:43:26+00:00",
    sources_scanned: int = 3,
) -> dict:
    """Build a minimal Step Functions context event for tests."""
    deals = evaluated_deals if evaluated_deals is not None else []
    return {
        "new_deal_ids": [d["deal_id"] for d in deals],
        "sources_scanned": sources_scanned,
        "deals_discovered": len(deals),
        "scanned_at": scanned_at,
        "evaluated_deals": deals,
    }


# ─────────────────────────────────────────────
# PipelineSummaryAgent._should_notify
# ─────────────────────────────────────────────


class TestShouldNotify:
    """Tests for PipelineSummaryAgent._should_notify."""

    def test_returns_true_when_no_dedup_table_configured(self) -> None:
        """With no dedup_table_name, the check always returns True (always notify)."""
        config = _make_config(dedup_table_name="")
        agent = PipelineSummaryAgent(config=config)
        assert agent._should_notify() is True

    def test_returns_true_on_first_write(self) -> None:
        """A successful conditional write means the key was absent — return True."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)

        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        with patch.object(
            type(agent),
            "dynamodb",
            new_callable=lambda: property(
                lambda self: MagicMock(Table=lambda name: mock_table)
            ),
        ):
            result = agent._should_notify()

        assert result is True
        mock_table.put_item.assert_called_once()
        call_kwargs = mock_table.put_item.call_args[1]
        assert call_kwargs["Item"]["pk"] == "no-deals-notif"
        assert "expires_at" in call_kwargs["Item"]

    def test_returns_false_when_dedup_key_exists(self) -> None:
        """ConditionalCheckFailedException means within 24-hour window — return False."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)

        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": ""}},
            "PutItem",
        )

        with patch.object(
            type(agent),
            "dynamodb",
            new_callable=lambda: property(
                lambda self: MagicMock(Table=lambda name: mock_table)
            ),
        ):
            result = agent._should_notify()

        assert result is False

    def test_fails_open_on_unexpected_dynamodb_error(self) -> None:
        """Unexpected DynamoDB errors should fail open so users still get notified."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)

        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": ""}},
            "PutItem",
        )

        with patch.object(
            type(agent),
            "dynamodb",
            new_callable=lambda: property(
                lambda self: MagicMock(Table=lambda name: mock_table)
            ),
        ):
            result = agent._should_notify()

        assert result is True


# ─────────────────────────────────────────────
# PipelineSummaryAgent.run
# ─────────────────────────────────────────────


class TestPipelineSummaryAgentRun:
    """Tests for PipelineSummaryAgent.run."""

    async def test_no_action_when_high_value_deal_found(self) -> None:
        """When at least one deal is high-value, no dedup check or SQS publish occurs."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)

        event = _make_event(evaluated_deals=[
            {"deal_id": "abc", "is_high_value": True, "discount_percentage": 30.0},
            {"deal_id": "def", "is_high_value": False, "discount_percentage": 5.0},
        ])

        with (
            patch.object(agent, "_should_notify") as mock_dedup,
            patch.object(agent, "_enqueue_no_deals") as mock_enqueue,
        ):
            result = await agent.run(event)

        mock_dedup.assert_not_called()
        mock_enqueue.assert_not_called()
        assert result == event

    async def test_sqs_sent_when_zero_deals_discovered(self) -> None:
        """When the scanner finds no new deals (empty evaluated_deals), SQS is published."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        event = _make_event(
            evaluated_deals=[],
            scanned_at="2026-03-06T17:43:26+00:00",
            sources_scanned=3,
        )

        with (
            patch.object(agent, "_should_notify", return_value=True),
            patch.object(agent, "_enqueue_no_deals") as mock_enqueue,
        ):
            result = await agent.run(event)

        mock_enqueue.assert_called_once_with("2026-03-06T17:43:26+00:00", 3)
        assert result == event

    async def test_sqs_sent_when_deals_exist_but_none_high_value(self) -> None:
        """When deals are evaluated but none are high-value, SQS is published."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        event = _make_event(evaluated_deals=[
            {"deal_id": "abc", "is_high_value": False, "discount_percentage": 5.0},
            {"deal_id": "def", "is_high_value": False, "discount_percentage": 10.0},
        ])

        with (
            patch.object(agent, "_should_notify", return_value=True),
            patch.object(agent, "_enqueue_no_deals") as mock_enqueue,
        ):
            result = await agent.run(event)

        mock_enqueue.assert_called_once()
        assert result == event

    async def test_dedup_suppresses_notification(self) -> None:
        """When _should_notify returns False (within 24h window), SQS is not published."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        event = _make_event(evaluated_deals=[])

        with (
            patch.object(agent, "_should_notify", return_value=False),
            patch.object(agent, "_enqueue_no_deals") as mock_enqueue,
        ):
            result = await agent.run(event)

        mock_enqueue.assert_not_called()
        assert result == event

    async def test_returns_event_unchanged(self) -> None:
        """The run method always returns the input event unchanged for Step Functions."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        event = _make_event(evaluated_deals=[
            {"deal_id": "abc", "is_high_value": True, "discount_percentage": 25.0},
        ])

        result = await agent.run(event)

        assert result is event
