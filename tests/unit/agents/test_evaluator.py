"""Unit tests for EvaluatorAgent.

Uses an in-memory SQLite database and a mock BedrockPriceEstimator to
exercise discount calculation and deal status transitions without
making real AWS API calls.
"""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from dealfinder.agents.bedrock import PriceEstimationResult
from dealfinder.agents.config import AgentConfig
from dealfinder.agents.evaluator import EvaluatorAgent
from dealfinder.data.repository import DealRepository, PriceEstimateRepository
from dealfinder.db.models import Base, Deal, DealSource, DealStatus


def _make_estimator(
    estimated_price: float,
    confidence: float = 0.85,
    range_low: float | None = None,
    range_high: float | None = None,
) -> MagicMock:
    """Return a mock BedrockPriceEstimator with a fixed result."""
    result = PriceEstimationResult(
        estimated_price=Decimal(str(estimated_price)),
        confidence=Decimal(str(confidence)),
        range_low=Decimal(str(range_low)) if range_low else None,
        range_high=Decimal(str(range_high)) if range_high else None,
        model_id="mock-model",
        inference_time_ms=100,
    )
    mock = MagicMock()
    mock.estimate_price.return_value = result
    return mock


@pytest.fixture
async def engine():
    """In-memory SQLite engine."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(eng.sync_engine, "connect")
    def _pragma(dbapi_conn, _record):
        """Enable foreign keys for SQLite."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng
    await eng.dispose()


@pytest.fixture
async def db_session(engine):
    """Open database session."""
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest.fixture
async def source(db_session) -> DealSource:
    """Persisted active DealSource."""
    src = DealSource(
        name="Test Feed",
        url="https://example.com/feed.rss",
        category="electronics",
        is_active=True,
    )
    db_session.add(src)
    await db_session.commit()
    await db_session.refresh(src)
    return src


@pytest.fixture
async def deal_with_price(db_session, source: DealSource) -> Deal:
    """Persisted Deal with sale_price set."""
    deal = Deal(
        source_id=source.id,
        external_id="deal-001",
        title="Sony WH-1000XM5 Headphones",
        description="Premium noise-cancelling headphones",
        url="https://example.com/deal",
        sale_price=Decimal("199.99"),
        category="electronics",
        brand="Sony",
        status=DealStatus.DISCOVERED,
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    return deal


@pytest.fixture
async def deal_no_price(db_session, source: DealSource) -> Deal:
    """Persisted Deal with no price information."""
    deal = Deal(
        source_id=source.id,
        external_id="deal-no-price",
        title="Mystery Item",
        url="https://example.com/mystery",
        status=DealStatus.DISCOVERED,
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    return deal


@pytest.fixture
async def deal_with_zero_sale_price(db_session, source: DealSource) -> Deal:
    """Persisted Deal with sale_price explicitly set to $0.00 (a free item).

    original_price is set to a non-zero value so a falsy-check regression
    would silently use that instead of the correct $0.00 sale price.
    """
    deal = Deal(
        source_id=source.id,
        external_id="deal-free",
        title="Free Widget",
        url="https://example.com/free",
        sale_price=Decimal("0.00"),
        original_price=Decimal("50.00"),
        status=DealStatus.DISCOVERED,
    )
    db_session.add(deal)
    await db_session.commit()
    await db_session.refresh(deal)
    return deal


@pytest.fixture
def config() -> AgentConfig:
    """Agent config with 20% discount threshold."""
    return AgentConfig(
        discount_threshold=20.0,
        bedrock_region="us-east-1",
        bedrock_model_id="mock",
        notification_queue_url="",
    )


class TestEvaluatorAgentCalculateDiscount:
    """Tests for EvaluatorAgent._calculate_discount."""

    def test_standard_discount(self, config: AgentConfig) -> None:
        """50% off from $400 estimated → 50% discount."""
        agent = EvaluatorAgent(config=config, estimator=MagicMock())
        discount = agent._calculate_discount(
            sale_price=Decimal("200.00"),
            estimated_value=Decimal("400.00"),
        )
        assert discount == Decimal("50.00")

    def test_no_discount_when_sale_equals_estimate(self, config: AgentConfig) -> None:
        """Sale price equal to estimated value → 0% discount."""
        agent = EvaluatorAgent(config=config, estimator=MagicMock())
        discount = agent._calculate_discount(
            sale_price=Decimal("100.00"),
            estimated_value=Decimal("100.00"),
        )
        assert discount == Decimal("0.00")

    def test_zero_estimated_value_returns_zero(self, config: AgentConfig) -> None:
        """Estimated value of zero should return 0% to avoid division by zero."""
        agent = EvaluatorAgent(config=config, estimator=MagicMock())
        discount = agent._calculate_discount(
            sale_price=Decimal("10.00"),
            estimated_value=Decimal("0.00"),
        )
        assert discount == Decimal("0")

    def test_clamps_negative_discount_to_zero(self, config: AgentConfig) -> None:
        """Sale price above estimated value should clamp to 0%, not go negative."""
        agent = EvaluatorAgent(config=config, estimator=MagicMock())
        discount = agent._calculate_discount(
            sale_price=Decimal("150.00"),
            estimated_value=Decimal("100.00"),
        )
        assert discount == Decimal("0.00")


class TestEvaluatorAgentEvaluateDeal:
    """Tests for EvaluatorAgent.evaluate_deal using in-memory SQLite."""

    async def test_high_value_deal_marked_correctly(
        self, engine, deal_with_price: Deal, config: AgentConfig
    ) -> None:
        """Deal with >20% discount should be marked as high value and EVALUATED."""
        # Estimated price of $300 gives (300-200)/300 = 33% discount
        estimator = _make_estimator(estimated_price=300.0, confidence=0.9)
        agent = EvaluatorAgent(config=config, estimator=estimator)

        # Patch get_async_session to use our test engine
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        import dealfinder.agents.evaluator as evaluator_module
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _test_session():
            async with factory() as s:
                yield s

        original = evaluator_module.get_async_session
        evaluator_module.get_async_session = _test_session

        try:
            result = await agent.evaluate_deal(deal_with_price.id)
        finally:
            evaluator_module.get_async_session = original

        assert result["status"] == "evaluated"
        assert result["is_high_value"] is True
        assert result["discount_percentage"] > 20.0
        assert result["estimated_value"] == 300.0

    async def test_below_threshold_deal_not_high_value(
        self, engine, deal_with_price: Deal, config: AgentConfig
    ) -> None:
        """Deal with <20% discount should be EVALUATED but not marked high value."""
        # Estimated price of $220 gives (220-200)/220 ≈ 9% discount — below threshold
        estimator = _make_estimator(estimated_price=220.0, confidence=0.75)
        agent = EvaluatorAgent(config=config, estimator=estimator)

        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        import dealfinder.agents.evaluator as evaluator_module
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _test_session():
            async with factory() as s:
                yield s

        original = evaluator_module.get_async_session
        evaluator_module.get_async_session = _test_session

        try:
            result = await agent.evaluate_deal(deal_with_price.id)
        finally:
            evaluator_module.get_async_session = original

        assert result["status"] == "evaluated"
        assert result["is_high_value"] is False
        assert result["discount_percentage"] < 20.0

    async def test_deal_not_found_returns_not_found_status(
        self, engine, config: AgentConfig
    ) -> None:
        """Non-existent deal_id should return not_found status."""
        agent = EvaluatorAgent(config=config, estimator=MagicMock())

        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        import dealfinder.agents.evaluator as evaluator_module
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _test_session():
            async with factory() as s:
                yield s

        original = evaluator_module.get_async_session
        evaluator_module.get_async_session = _test_session

        try:
            result = await agent.evaluate_deal(uuid4())
        finally:
            evaluator_module.get_async_session = original

        assert result["status"] == "not_found"
        assert result["is_high_value"] is False

    async def test_zero_sale_price_is_evaluated_not_rejected(
        self, engine, deal_with_zero_sale_price: Deal, config: AgentConfig
    ) -> None:
        """Deal with sale_price=Decimal('0.00') must be evaluated, not rejected.

        Decimal('0.00') is falsy in Python, so a naive `or`-based check would
        fall through to original_price ($50.00).  The explicit `is not None`
        check must use $0.00, yielding a 100% discount when estimated at $10.
        """
        estimator = _make_estimator(estimated_price=10.0, confidence=0.9)
        agent = EvaluatorAgent(config=config, estimator=estimator)

        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        import dealfinder.agents.evaluator as evaluator_module
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _test_session():
            async with factory() as s:
                yield s

        original = evaluator_module.get_async_session
        evaluator_module.get_async_session = _test_session

        try:
            result = await agent.evaluate_deal(deal_with_zero_sale_price.id)
        finally:
            evaluator_module.get_async_session = original

        assert result["status"] == "evaluated"
        assert result["discount_percentage"] == 100.0  # (10 - 0) / 10 * 100
        assert result["is_high_value"] is True

    async def test_deal_with_no_price_is_rejected(
        self, engine, deal_no_price: Deal, config: AgentConfig
    ) -> None:
        """Deal with neither sale_price nor original_price should be REJECTED."""
        agent = EvaluatorAgent(config=config, estimator=MagicMock())

        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        import dealfinder.agents.evaluator as evaluator_module
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _test_session():
            async with factory() as s:
                yield s

        original = evaluator_module.get_async_session
        evaluator_module.get_async_session = _test_session

        try:
            result = await agent.evaluate_deal(deal_no_price.id)
        finally:
            evaluator_module.get_async_session = original

        assert result["status"] == "rejected"
        assert result["is_high_value"] is False

    async def test_bedrock_failure_rejects_deal(
        self, engine, deal_with_price: Deal, config: AgentConfig
    ) -> None:
        """Bedrock estimation failure should mark deal as REJECTED."""
        failing_estimator = MagicMock()
        failing_estimator.estimate_price.side_effect = RuntimeError("Bedrock timeout")
        agent = EvaluatorAgent(config=config, estimator=failing_estimator)

        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        import dealfinder.agents.evaluator as evaluator_module
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _test_session():
            async with factory() as s:
                yield s

        original = evaluator_module.get_async_session
        evaluator_module.get_async_session = _test_session

        try:
            result = await agent.evaluate_deal(deal_with_price.id)
        finally:
            evaluator_module.get_async_session = original

        assert result["status"] == "estimation_failed"
        assert result["is_high_value"] is False


class TestEvaluatorAgentRun:
    """Tests for EvaluatorAgent.run (event dispatch)."""

    async def test_run_requires_deal_id(self, config: AgentConfig) -> None:
        """run() should raise ValueError if deal_id is missing from event."""
        agent = EvaluatorAgent(config=config, estimator=MagicMock())
        with pytest.raises(ValueError, match="deal_id is required"):
            await agent.run({})

    async def test_run_passes_deal_id_to_evaluate(self, config: AgentConfig) -> None:
        """run() should forward the deal_id string to evaluate_deal as a UUID."""
        deal_id = uuid4()
        agent = EvaluatorAgent(config=config, estimator=MagicMock())

        # Mock evaluate_deal to avoid DB access
        async def _mock_evaluate(uid):
            return {"deal_id": str(uid), "status": "not_found", "is_high_value": False,
                    "discount_percentage": 0.0, "estimated_value": 0.0, "confidence": 0.0}

        agent.evaluate_deal = _mock_evaluate
        result = await agent.run({"deal_id": str(deal_id)})
        assert result["deal_id"] == str(deal_id)
