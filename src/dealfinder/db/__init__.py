"""Database module for Deal Finder.

This module provides SQLAlchemy models and database connectivity
for the Aurora PostgreSQL backend.
"""

from dealfinder.db.models import Base, Deal, User, PriceEstimate, DealSource, Notification
from dealfinder.db.connection import (
    DatabaseConfig,
    get_async_engine,
    get_async_session,
    async_session_factory,
)

__all__ = [
    # Models
    "Base",
    "Deal",
    "User",
    "PriceEstimate",
    "DealSource",
    "Notification",
    # Connection
    "DatabaseConfig",
    "get_async_engine",
    "get_async_session",
    "async_session_factory",
]
