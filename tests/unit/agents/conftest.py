"""Shared pytest fixtures and SQLAlchemy dialect overrides for agent unit tests.

Registers PostgreSQL-specific column types as their SQLite equivalents so that
in-memory SQLite engines can create tables defined with JSONB and UUID columns.
These registrations must live here (loaded once by pytest before any test
module) rather than in individual test files to avoid duplicate-registration
errors when both test_scanner and test_evaluator are collected in the same run.
"""

from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    """Render JSONB as JSON for SQLite."""
    return "JSON"


@compiles(PGUUID, "sqlite")
def _pguuid_sqlite(type_, compiler, **kw):
    """Render PostgreSQL UUID as CHAR(32) for SQLite."""
    return "CHAR(32)"
