from __future__ import annotations

"""
SQLite JSONB compilation helper for regression tests.

The production models use PostgreSQL's JSONB columns. When we recreate the
schema against in-memory SQLite during tests, SQLAlchemy needs to know how to
compile JSONB for the SQLite dialect. Importing this module once (typically in
pytest fixtures) registers a minimal compiler hook that maps JSONB columns to
SQLite's native JSON type so metadata creation succeeds.
"""

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(element: JSONB, compiler, **_: object) -> str:
    """Render PostgreSQL JSONB columns as SQLite JSON."""
    return "JSON"


def enable_sqlite_jsonb_support() -> None:
    """Backward-compatible no-op helper for call sites that expect a callable."""
    # Import side effects already registered the compiler patch.
    return None
