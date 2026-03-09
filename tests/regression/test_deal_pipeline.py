from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from dealfinder.agents.config import AgentConfig
from dealfinder.agents.evaluator import EvaluatorAgent
from dealfinder.agents.scanner import ScannerAgent
from dealfinder.data.repository import DealRepository
from dealfinder.db.models import Deal, DealSource, DealStatus

pytestmark = pytest.mark.asyncio


class _StubQueue:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def send_message(self, QueueUrl: str, MessageBody: str) -> dict[str, str]:
        self.messages.append({"QueueUrl": QueueUrl, "MessageBody": MessageBody})
        return {"MessageId": "stubbed-message"}


class _SessionContext:
    def __init__(self, factory) -> None:
        self._factory = factory
        self._session = None

    async def __aenter__(self):
        self._session = self._factory()
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        if not self._session:
            return
        if exc_type:
            await self._session.rollback()
        else:
            await self._session.commit()
        await self._session.close()


def _make_feed(*entries: dict) -> SimpleNamespace:
    return SimpleNamespace(entries=list(entries), bozo=False, bozo_exception=None)


def _build_agent_config(queue_url: str, discount_threshold: float = 20.0) -> AgentConfig:
    config = AgentConfig()
    config.notification_queue_url = queue_url
    config.discount_threshold = discount_threshold
    config.bedrock_region = "us-east-1"
    return config


def _prepare_source(session, name: str, url: str) -> DealSource:
    source = DealSource(name=name, url=url, is_active=True)
    session.add(source)
    return source


def _prepare_estimator(estimated_price: Decimal, confidence: Decimal = Decimal("0.90")):
    estimation = SimpleNamespace(
        model_id="anthropic.mock",
        estimated_price=estimated_price,
        confidence=confidence,
        range_low=estimated_price * Decimal("0.9"),
        range_high=estimated_price * Decimal("1.1"),
        inference_time_ms=1234,
    )

    class _Estimator:
        def estimate_price(self, **_) -> SimpleNamespace:
            return estimation

    return _Estimator()


async def _create_pipeline_deal(session, source: DealSource, title: str, link: str) -> Deal:
    feed = _make_feed(
        {
            "id": f"{title}-id",
            "title": title,
            "link": link,
            "summary": "Regression pipeline entry",
            "published": "2026-03-07T00:00:00Z",
            "tags": [{"term": "electronics"}],
        }
    )
    scanner = ScannerAgent()
    await session.flush()
    with pytest.MonkeyPatch.context() as monkey:
        monkey.setattr("dealfinder.agents.scanner.feedparser.parse", lambda _: feed)
        new_deals = await scanner.scan_source(source, session)
    await session.commit()
    deal = new_deals[0]
    await session.refresh(deal)
    return deal


async def _patch_evaluator_dependencies(
    monkeypatch,
    regression_session_factory,
    queue_stub: _StubQueue,
    saved_feeds: list[dict[str, str]],
):
    class _DummyUser:
        def __init__(self, feeds: list[dict[str, str]]) -> None:
            self.id = uuid4()
            self.notification_preferences = {"saved_feeds": feeds}

    async def _fake_find_active_users(self):
        return [_DummyUser(saved_feeds)]

    monkeypatch.setattr(
        "dealfinder.agents.evaluator.UserRepository.find_active_users",
        _fake_find_active_users,
        raising=False,
    )
    monkeypatch.setattr(
        "dealfinder.agents.evaluator.get_async_session",
        lambda: _SessionContext(regression_session_factory),
        raising=False,
    )
    monkeypatch.setattr(
        "dealfinder.agents.evaluator.boto3.client",
        lambda *_args, **_kwargs: queue_stub,
    )


async def _verify_deal_status(regression_session_factory, deal_id):
    async with _SessionContext(regression_session_factory) as session:
        repo = DealRepository(session)
        refreshed = await repo.get_by_id(deal_id)
        assert refreshed is not None
        return refreshed


async def _reset_tables(regression_session_factory):
    async with _SessionContext(regression_session_factory) as session:
        await session.execute(text("DELETE FROM notifications"))
        await session.execute(text("DELETE FROM price_estimates"))
        await session.execute(text("DELETE FROM deals"))
        await session.execute(text("DELETE FROM deal_sources"))


async def test_high_value_deal_triggers_notification_queue(
    regression_session_factory,
    monkeypatch,
    pipeline_env_variables,
):
    await _reset_tables(regression_session_factory)
    async with _SessionContext(regression_session_factory) as session:
        source = _prepare_source(session, "Regression Feed HV", "https://example.com/feed/high")
        await session.commit()
        await session.refresh(source)
        deal = await _create_pipeline_deal(
            session, source, "Mega Laptop Deal", "https://example.com/deals/high"
        )
        deal.sale_price = Decimal("100")
        deal.original_price = Decimal("300")
        await session.commit()
        deal_id = deal.id

    queue_stub = _StubQueue()
    saved_feeds = [{"id": "feed-laptop", "query": "Mega Laptop"}]
    await _patch_evaluator_dependencies(
        monkeypatch, regression_session_factory, queue_stub, saved_feeds
    )

    config = _build_agent_config(pipeline_env_variables["sqs_queue_url"], discount_threshold=20.0)
    evaluator = EvaluatorAgent(config=config)
    evaluator.estimator = _prepare_estimator(estimated_price=Decimal("400"))

    result = await evaluator.evaluate_deal(deal_id)

    assert result["status"] == "evaluated"
    assert result["is_high_value"] is True
    assert result["discount_percentage"] == pytest.approx(75.0, rel=1e-6)
    assert queue_stub.messages, "Expected SQS message for high-value deal"
    message = queue_stub.messages[0]
    assert message["QueueUrl"] == pipeline_env_variables["sqs_queue_url"]
    assert json.loads(message["MessageBody"])["deal_id"] == str(deal_id)
    assert result["matched_feed_pairs"]
    refreshed_deal = await _verify_deal_status(regression_session_factory, deal_id)
    assert refreshed_deal.status == DealStatus.EVALUATED
    assert refreshed_deal.is_high_value is True
    assert refreshed_deal.discount_percentage is not None


async def test_sub_threshold_deal_skips_notification_queue(
    regression_session_factory,
    monkeypatch,
    pipeline_env_variables,
):
    await _reset_tables(regression_session_factory)
    async with _SessionContext(regression_session_factory) as session:
        source = _prepare_source(session, "Regression Feed LV", "https://example.com/feed/low")
        await session.commit()
        await session.refresh(source)
        deal = await _create_pipeline_deal(
            session, source, "Budget Mouse Deal", "https://example.com/deals/low"
        )
        deal.sale_price = Decimal("95")
        deal.original_price = Decimal("100")
        await session.commit()
        deal_id = deal.id

    queue_stub = _StubQueue()
    saved_feeds = [{"id": "feed-mouse", "query": "Office Chair"}]
    await _patch_evaluator_dependencies(
        monkeypatch, regression_session_factory, queue_stub, saved_feeds
    )

    config = _build_agent_config(pipeline_env_variables["sqs_queue_url"], discount_threshold=20.0)
    evaluator = EvaluatorAgent(config=config)
    evaluator.estimator = _prepare_estimator(estimated_price=Decimal("105"))

    result = await evaluator.evaluate_deal(deal_id)

    assert result["status"] == "evaluated"
    assert result["is_high_value"] is False
    assert result["matched_feed_pairs"] == []
    assert queue_stub.messages == [], "No SQS messages should be sent for sub-threshold deals"
    refreshed_deal = await _verify_deal_status(regression_session_factory, deal_id)
    assert refreshed_deal.status == DealStatus.EVALUATED
    assert refreshed_deal.is_high_value is False
    assert refreshed_deal.discount_percentage is not None
    assert refreshed_deal.discount_percentage < Decimal("20")


async def test_watchlist_dedup_sends_single_notification(
    regression_session_factory,
    monkeypatch,
    pipeline_env_variables,
):
    await _reset_tables(regression_session_factory)
    async with _SessionContext(regression_session_factory) as session:
        source = _prepare_source(session, "Regression Feed WL", "https://example.com/feed/watch")
        await session.commit()
        await session.refresh(source)
        deal = await _create_pipeline_deal(
            session, source, "Ultimate Gaming Rig", "https://example.com/deals/watch"
        )
        deal.sale_price = Decimal("500")
        deal.original_price = Decimal("1200")
        await session.commit()
        deal_id = deal.id

    queue_stub = _StubQueue()
    saved_feeds = [
        {"id": "feed-gaming-1", "query": "Ultimate Gaming"},
        {"id": "feed-gaming-2", "query": "Gaming Rig Ultimate"},
        {"id": "feed-miss", "query": "Office Chair"},
    ]
    await _patch_evaluator_dependencies(
        monkeypatch, regression_session_factory, queue_stub, saved_feeds
    )

    config = _build_agent_config(pipeline_env_variables["sqs_queue_url"], discount_threshold=25.0)
    evaluator = EvaluatorAgent(config=config)
    evaluator.estimator = _prepare_estimator(estimated_price=Decimal("1500"))

    result = await evaluator.evaluate_deal(deal_id)

    assert result["is_high_value"] is True
    assert len(result["matched_feed_pairs"]) == 2
    assert len(queue_stub.messages) == 1, "Queue should receive a single message per deal"
    message_body = json.loads(queue_stub.messages[0]["MessageBody"])
    assert message_body["deal_id"] == str(deal_id)
    refreshed_deal = await _verify_deal_status(regression_session_factory, deal_id)
    assert refreshed_deal.is_high_value is True
