"""Unit tests for PipelineSummaryAgent.

Uses mocked DynamoDB, SQS, and database clients so no AWS services or real
databases are required.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

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
        "new_deal_ids": [d.get("deal_id", "") for d in deals],
        "sources_scanned": sources_scanned,
        "deals_discovered": len(deals),
        "scanned_at": scanned_at,
        "evaluated_deals": deals,
    }


def _make_mock_user(
    user_id: str | None = None,
    saved_feeds: list | None = None,
) -> MagicMock:
    """Build a mock User with optional saved_feeds in notification_preferences."""
    uid = user_id or str(uuid4())
    user = MagicMock()
    user.id = UUID(uid)
    feeds = saved_feeds if saved_feeds is not None else []
    user.notification_preferences = {"saved_feeds": feeds}
    return user


# ─────────────────────────────────────────────
# PipelineSummaryAgent._check_and_set_dedup
# ─────────────────────────────────────────────


class TestCheckAndSetDedup:
    """Tests for PipelineSummaryAgent._check_and_set_dedup."""

    def test_returns_true_when_no_dedup_table_configured(self) -> None:
        """With no dedup_table_name, the check always returns True (always notify)."""
        config = _make_config(dedup_table_name="")
        agent = PipelineSummaryAgent(config=config)
        assert agent._check_and_set_dedup("no-deals-feed#uid#fid") is True

    def test_returns_true_on_first_write(self) -> None:
        """A successful conditional write means the key was absent — return True."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        dedup_key = "no-deals-feed#user-1#feed-1"

        mock_table = MagicMock()
        mock_table.put_item.return_value = {}

        with patch.object(
            type(agent),
            "dynamodb",
            new_callable=lambda: property(
                lambda self: MagicMock(Table=lambda name: mock_table)
            ),
        ):
            result = agent._check_and_set_dedup(dedup_key)

        assert result is True
        mock_table.put_item.assert_called_once()
        call_kwargs = mock_table.put_item.call_args[1]
        assert call_kwargs["Item"]["pk"] == dedup_key
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
            result = agent._check_and_set_dedup("no-deals-feed#uid#fid")

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
            result = agent._check_and_set_dedup("no-deals-feed#uid#fid")

        assert result is True


# ─────────────────────────────────────────────
# PipelineSummaryAgent._check_unmatched_feeds
# ─────────────────────────────────────────────


class TestCheckUnmatchedFeeds:
    """Tests for PipelineSummaryAgent._check_unmatched_feeds."""

    def _make_mock_session(self, users: list) -> tuple:
        """Return (mock_session, mock_user_repo) with find_active_users seeded."""
        mock_user_repo = AsyncMock()
        mock_user_repo.find_active_users.return_value = users
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session, mock_user_repo

    async def test_no_enqueue_when_no_users(self) -> None:
        """With no active users, nothing is enqueued."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        mock_session, mock_user_repo = self._make_mock_session(users=[])

        with (
            patch("dealfinder.agents.pipeline_summary.get_async_session", return_value=mock_session),
            patch("dealfinder.agents.pipeline_summary.UserRepository", return_value=mock_user_repo),
            patch.object(agent, "_enqueue_no_deals_feed") as mock_enqueue,
        ):
            await agent._check_unmatched_feeds(matched_pairs=[], scanned_at="2026-03-06T17:43:26+00:00")

        mock_enqueue.assert_not_called()

    async def test_enqueues_for_unmatched_feed(self) -> None:
        """An unmatched feed triggers a dedup check and a no_deals_feed SQS message."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        user_id = str(uuid4())
        feed_id = "feed-abc"
        feed_name = "Sony headphones"
        user = _make_mock_user(user_id=user_id, saved_feeds=[
            {"id": feed_id, "query": feed_name, "min_discount": 0},
        ])
        mock_session, mock_user_repo = self._make_mock_session(users=[user])

        with (
            patch("dealfinder.agents.pipeline_summary.get_async_session", return_value=mock_session),
            patch("dealfinder.agents.pipeline_summary.UserRepository", return_value=mock_user_repo),
            patch.object(agent, "_check_and_set_dedup", return_value=True),
            patch.object(agent, "_enqueue_no_deals_feed") as mock_enqueue,
        ):
            await agent._check_unmatched_feeds(
                matched_pairs=[],
                scanned_at="2026-03-06T17:43:26+00:00",
            )

        mock_enqueue.assert_called_once_with(
            user_id=user_id,
            feed_id=feed_id,
            feed_name=feed_name,
            timestamp="2026-03-06T17:43:26+00:00",
        )

    async def test_no_enqueue_when_feed_is_matched(self) -> None:
        """A feed that produced a deal match this run is not notified."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        user_id = str(uuid4())
        feed_id = "feed-xyz"
        user = _make_mock_user(user_id=user_id, saved_feeds=[
            {"id": feed_id, "query": "Apple AirPods", "min_discount": 0},
        ])
        mock_session, mock_user_repo = self._make_mock_session(users=[user])
        matched_pairs = [{"user_id": user_id, "feed_id": feed_id, "feed_name": "Apple AirPods"}]

        with (
            patch("dealfinder.agents.pipeline_summary.get_async_session", return_value=mock_session),
            patch("dealfinder.agents.pipeline_summary.UserRepository", return_value=mock_user_repo),
            patch.object(agent, "_check_and_set_dedup") as mock_dedup,
            patch.object(agent, "_enqueue_no_deals_feed") as mock_enqueue,
        ):
            await agent._check_unmatched_feeds(
                matched_pairs=matched_pairs,
                scanned_at="2026-03-06T17:43:26+00:00",
            )

        mock_dedup.assert_not_called()
        mock_enqueue.assert_not_called()

    async def test_dedup_suppresses_notification(self) -> None:
        """When dedup key already exists (24h window), no SQS message is sent."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        user_id = str(uuid4())
        user = _make_mock_user(user_id=user_id, saved_feeds=[
            {"id": "feed-1", "query": "Laptop", "min_discount": 0},
        ])
        mock_session, mock_user_repo = self._make_mock_session(users=[user])

        with (
            patch("dealfinder.agents.pipeline_summary.get_async_session", return_value=mock_session),
            patch("dealfinder.agents.pipeline_summary.UserRepository", return_value=mock_user_repo),
            patch.object(agent, "_check_and_set_dedup", return_value=False),
            patch.object(agent, "_enqueue_no_deals_feed") as mock_enqueue,
        ):
            await agent._check_unmatched_feeds(matched_pairs=[], scanned_at="")

        mock_enqueue.assert_not_called()

    async def test_feed_without_id_is_skipped(self) -> None:
        """Feeds missing an id field should be silently skipped."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        user = _make_mock_user(saved_feeds=[{"query": "Laptop", "min_discount": 0}])
        mock_session, mock_user_repo = self._make_mock_session(users=[user])

        with (
            patch("dealfinder.agents.pipeline_summary.get_async_session", return_value=mock_session),
            patch("dealfinder.agents.pipeline_summary.UserRepository", return_value=mock_user_repo),
            patch.object(agent, "_check_and_set_dedup") as mock_dedup,
            patch.object(agent, "_enqueue_no_deals_feed") as mock_enqueue,
        ):
            await agent._check_unmatched_feeds(matched_pairs=[], scanned_at="")

        mock_dedup.assert_not_called()
        mock_enqueue.assert_not_called()

    async def test_db_failure_logged_not_raised(self) -> None:
        """If loading users from the DB fails the error is logged and nothing is enqueued."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("dealfinder.agents.pipeline_summary.get_async_session", return_value=mock_session),
            patch.object(agent, "_enqueue_no_deals_feed") as mock_enqueue,
        ):
            # Should not raise
            await agent._check_unmatched_feeds(matched_pairs=[], scanned_at="")

        mock_enqueue.assert_not_called()


# ─────────────────────────────────────────────
# PipelineSummaryAgent.run
# ─────────────────────────────────────────────


class TestPipelineSummaryAgentRun:
    """Tests for PipelineSummaryAgent.run."""

    async def test_aggregates_matched_feed_pairs_from_deals(self) -> None:
        """matched_feed_pairs from all deals are combined before _check_unmatched_feeds."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        pair_a = {"user_id": "u1", "feed_id": "f1", "feed_name": "Sony"}
        pair_b = {"user_id": "u2", "feed_id": "f2", "feed_name": "Apple"}
        event = _make_event(evaluated_deals=[
            {"deal_id": "d1", "is_high_value": False, "matched_feed_pairs": [pair_a]},
            {"deal_id": "d2", "is_high_value": True, "matched_feed_pairs": [pair_b]},
        ])

        with patch.object(
            agent, "_check_unmatched_feeds", new_callable=AsyncMock
        ) as mock_check:
            await agent.run(event)

        called_pairs = mock_check.call_args[0][0]
        assert pair_a in called_pairs
        assert pair_b in called_pairs

    async def test_calls_check_unmatched_feeds_for_high_value_run(self) -> None:
        """_check_unmatched_feeds is called even when high-value deals are present."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        event = _make_event(evaluated_deals=[
            {"deal_id": "abc", "is_high_value": True, "matched_feed_pairs": []},
        ])

        with patch.object(
            agent, "_check_unmatched_feeds", new_callable=AsyncMock
        ) as mock_check:
            result = await agent.run(event)

        mock_check.assert_awaited_once()
        assert result is event

    async def test_calls_check_unmatched_feeds_for_empty_run(self) -> None:
        """_check_unmatched_feeds is called even when no deals were evaluated."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        event = _make_event(evaluated_deals=[])

        with patch.object(
            agent, "_check_unmatched_feeds", new_callable=AsyncMock
        ) as mock_check:
            result = await agent.run(event)

        mock_check.assert_awaited_once_with([], event["scanned_at"])
        assert result is event

    async def test_returns_event_unchanged(self) -> None:
        """The run method always returns the input event unchanged for Step Functions."""
        config = _make_config()
        agent = PipelineSummaryAgent(config=config)
        event = _make_event(evaluated_deals=[
            {"deal_id": "abc", "is_high_value": True, "matched_feed_pairs": []},
        ])

        with patch.object(agent, "_check_unmatched_feeds", new_callable=AsyncMock):
            result = await agent.run(event)

        assert result is event
