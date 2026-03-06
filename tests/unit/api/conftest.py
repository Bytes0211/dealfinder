"""Shared pytest fixtures for API unit tests.

Provides:
- In-memory SQLite engine and session
- FastAPI TestClient with the database session overridden
- Pre-seeded User and Deal fixtures
"""

import bcrypt
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from dealfinder.api.deps import get_db
from dealfinder.api.main import app
from dealfinder.db.models import Base, Deal, DealSource, DealStatus, User


# ─────────────────────────────────────────────
# PostgreSQL type overrides for SQLite
# ─────────────────────────────────────────────

@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    """Render JSONB as JSON for SQLite."""
    return "JSON"


@compiles(PGUUID, "sqlite")
def _pguuid_sqlite(type_, compiler, **kw):
    """Render PostgreSQL UUID as CHAR(32) for SQLite."""
    return "CHAR(32)"


# ─────────────────────────────────────────────
# Database fixtures
# ─────────────────────────────────────────────


@pytest.fixture
async def engine():
    """In-memory SQLite engine with schema created."""
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
async def session(engine):
    """Open database session for direct ORM access in tests."""
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


@pytest.fixture
def client(engine):
    """FastAPI TestClient with the database session overridden to use SQLite."""
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ─────────────────────────────────────────────
# Entity fixtures
# ─────────────────────────────────────────────


@pytest.fixture
async def source(session) -> DealSource:
    """Persisted DealSource."""
    src = DealSource(
        name="Test Feed",
        url="https://example.com/feed.rss",
        is_active=True,
    )
    session.add(src)
    await session.commit()
    await session.refresh(src)
    return src


@pytest.fixture
async def deal(session, source) -> Deal:
    """Persisted high-value Deal."""
    d = Deal(
        source=source,
        source_id=source.id,
        external_id="ext-001",
        title="Sony WH-1000XM5 Headphones",
        url="https://example.com/sony",
        sale_price=Decimal("179.99"),
        original_price=Decimal("349.99"),
        estimated_value=Decimal("320.00"),
        discount_percentage=Decimal("48.57"),
        is_high_value=True,
        brand="Sony",
        status=DealStatus.EVALUATED,
    )
    session.add(d)
    await session.commit()
    await session.refresh(d)
    return d


@pytest.fixture
async def user(session) -> User:
    """Persisted active User."""
    u = User(
        email="test@example.com",
        username="testuser",
        hashed_password=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
        full_name="Test User",
        is_active=True,
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u
