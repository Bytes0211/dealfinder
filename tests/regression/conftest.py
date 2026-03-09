from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from dealfinder.db.models import Base

from .jsonb_patch import enable_sqlite_jsonb_support

"""Shared fixtures for regression test suite covering the deal pipeline."""

FAKE_AWS_ENVIRONMENT = {
    "sns_topic_arn": "arn:aws:sns:us-east-1:000000000000:regression-deal-events",
    "sqs_queue_url": "https://sqs.us-east-1.amazonaws.com/000000000000/regression-deal-queue",
    "dynamodb_table": "deal-notification-state",
    "verified_email": "regression@example.com",
}


@pytest_asyncio.fixture
async def sqlite_engine() -> AsyncIterator[AsyncEngine]:
    enable_sqlite_jsonb_support()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        poolclass=StaticPool,
    )

    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    event.listen(engine.sync_engine, "connect", _enable_foreign_keys)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
def regression_session_factory(
    sqlite_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(sqlite_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(
    regression_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    session = regression_session_factory()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()


@pytest.fixture(scope="session")
def regression_aws_environment() -> dict[str, str]:
    return FAKE_AWS_ENVIRONMENT.copy()


@pytest.fixture
def pipeline_env_variables(regression_aws_environment: dict[str, str]) -> Iterator[dict[str, str]]:
    overrides = {
        "DEALFINDER_SNS_TOPIC_ARN": regression_aws_environment["sns_topic_arn"],
        "DEALFINDER_SQS_QUEUE_URL": regression_aws_environment["sqs_queue_url"],
        "DEALFINDER_DYNAMODB_TABLE": regression_aws_environment["dynamodb_table"],
    }
    previous = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)
    try:
        yield regression_aws_environment
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
