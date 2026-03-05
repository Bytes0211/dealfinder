"""Lambda handler for running Alembic database migrations.

Invoke via ``scripts/run-migrations-lambda.sh`` which temporarily swaps the
Lambda handler to this module, invokes it synchronously, then restores the
original API handler.  This allows migrations to run inside the Lambda's VPC
where Aurora is accessible.

Usage (via script)::

    ./scripts/run-migrations-lambda.sh prod

Or directly::

    aws lambda invoke --function-name dealfinder-prod-api \\
        --payload '{"action": "migrate"}' response.json
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Run Alembic migrations and return a status summary.

    Args:
        event: Lambda event payload (unused; any payload triggers migration).
        context: Lambda context object (unused).

    Returns:
        Dict with ``status`` (``"success"`` or ``"error"``) and ``message``.
    """
    try:
        # Resolve DB credentials from Secrets Manager before running migrations
        _inject_db_env()

        # Locate alembic.ini relative to this file inside the Lambda package
        db_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_ini = os.path.join(db_dir, "alembic.ini")

        if not os.path.exists(alembic_ini):
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

        logger.info("Running Alembic migrations from %s", alembic_ini)

        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(alembic_ini)
        # Override script_location to absolute path so Alembic can find versions/
        alembic_cfg.set_main_option("script_location", os.path.join(db_dir, "alembic"))

        command.upgrade(alembic_cfg, "head")

        logger.info("Migrations completed successfully")
        return {"status": "success", "message": "Alembic upgrade head completed"}

    except Exception as exc:  # noqa: BLE001
        logger.exception("Migration failed: %s", exc)
        return {"status": "error", "message": str(exc)}


def _inject_db_env() -> None:
    """Fetch DB credentials from Secrets Manager and set them as env vars.

    Alembic's env.py calls ``DatabaseConfig()`` which reads plain env vars.
    This function ensures ``DB_PASSWORD`` and ``DB_USER`` are populated from
    the Secrets Manager secret before Alembic initialises its engine.
    """
    from dealfinder.db.connection import _resolve_db_config

    cfg = _resolve_db_config()
    os.environ.setdefault("DB_HOST", cfg.host)
    os.environ.setdefault("DB_NAME", cfg.name)
    os.environ["DB_USER"] = cfg.user
    os.environ["DB_PASSWORD"] = cfg.password.get_secret_value()
    logger.info("DB env vars populated (host=%s, db=%s, user=%s)", cfg.host, cfg.name, cfg.user)
