"""Database connection management for Deal Finder.

This module provides async database connectivity using SQLAlchemy
with connection pooling optimized for Aurora PostgreSQL.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseConfig(BaseSettings):
    """Database configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Connection
    host: str = "localhost"
    port: int = 5432
    name: str = "dealfinder"
    user: str = "dealfinder_admin"
    password: SecretStr = SecretStr("")

    # Connection pool
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800  # 30 minutes

    # SSL (required for Aurora)
    ssl_mode: str = "prefer"  # disable, allow, prefer, require, verify-ca, verify-full
    ssl_root_cert: Optional[str] = None

    # Debug
    echo: bool = False

    @property
    def async_url(self) -> str:
        """Generate async database URL for asyncpg."""
        password = self.password.get_secret_value()
        base_url = f"postgresql+asyncpg://{self.user}:{password}@{self.host}:{self.port}/{self.name}"
        
        # Add SSL parameters if needed
        params = []
        if self.ssl_mode != "disable":
            params.append(f"ssl={self.ssl_mode}")
        if self.ssl_root_cert:
            params.append(f"sslrootcert={self.ssl_root_cert}")
        
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url

    @property
    def sync_url(self) -> str:
        """Generate sync database URL for psycopg2 (used by Alembic)."""
        password = self.password.get_secret_value()
        base_url = f"postgresql://{self.user}:{password}@{self.host}:{self.port}/{self.name}"
        
        params = []
        if self.ssl_mode != "disable":
            params.append(f"sslmode={self.ssl_mode}")
        if self.ssl_root_cert:
            params.append(f"sslrootcert={self.ssl_root_cert}")
        
        if params:
            return f"{base_url}?{'&'.join(params)}"
        return base_url


# Global instances
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_async_engine(config: Optional[DatabaseConfig] = None) -> AsyncEngine:
    """Get or create the async database engine.

    Args:
        config: Database configuration. Uses environment variables if not provided.

    Returns:
        AsyncEngine instance with connection pooling configured.
    """
    global _engine

    if _engine is None:
        if config is None:
            config = DatabaseConfig()

        _engine = create_async_engine(
            config.async_url,
            echo=config.echo,
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
            pool_recycle=config.pool_recycle,
            pool_pre_ping=True,  # Verify connections before use
        )

    return _engine


def async_session_factory(
    engine: Optional[AsyncEngine] = None,
) -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory.

    Args:
        engine: Optional engine instance. Creates default if not provided.

    Returns:
        Session factory for creating database sessions.
    """
    global _session_factory

    if _session_factory is None:
        if engine is None:
            engine = get_async_engine()

        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _session_factory


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions.

    Yields:
        AsyncSession that is automatically committed on success
        or rolled back on exception.

    Example:
        async with get_async_session() as session:
            result = await session.execute(select(Deal))
            deals = result.scalars().all()
    """
    factory = async_session_factory()
    session = factory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def close_engine() -> None:
    """Close the database engine and release all connections."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
