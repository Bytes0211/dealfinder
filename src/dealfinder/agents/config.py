"""Agent configuration for Deal Finder Lambda functions.

Reads all settings from environment variables with the DEALFINDER_ prefix,
with sensible defaults suitable for local development.

Bedrock model IDs are loaded from config/bedrock_models.json as the default.
Set the DEALFINDER_BEDROCK_MODEL_ID environment variable to override per-Lambda.
"""

import json
import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_CONFIG_FILE = Path(__file__).resolve().parents[3] / "config" / "bedrock_models.json"


def _load_default_model_id() -> str:
    """Load the default Bedrock model ID from config/bedrock_models.json.

    Falls back to a hardcoded model ID if the config file is missing or
    cannot be parsed (e.g. inside a Lambda deployment package that does
    not include the config directory).

    Returns:
        Bedrock model ID string.
    """
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return data.get("default", "anthropic.claude-3-haiku-20240307-v1:0")
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        logger.debug("bedrock_models.json not found or unreadable (%s); using fallback", exc)
        return "anthropic.claude-3-haiku-20240307-v1:0"


class AgentConfig(BaseSettings):
    """Configuration for Lambda agent functions.

    Attributes:
        discount_threshold: Minimum discount percentage to flag a deal as high value.
        bedrock_region: AWS region used for Bedrock API calls.
        bedrock_model_id: Bedrock model identifier for Claude. Loaded from
            config/bedrock_models.json by default; override via
            DEALFINDER_BEDROCK_MODEL_ID env var.
        notification_queue_url: SQS URL for the notification-dispatch queue.
        ses_sender_email: Verified SES sender address for email notifications.
        sns_topic_arn: ARN of the SNS topic for deal alert fan-out.
        dedup_table_name: DynamoDB table used for 24-hour notification deduplication.
    """

    model_config = SettingsConfigDict(
        env_prefix="DEALFINDER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discount_threshold: float = 20.0
    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = _load_default_model_id()
    notification_queue_url: str = ""
    tavily_api_key: str = ""

    # Messenger Agent fields
    ses_sender_email: str = ""
    sns_topic_arn: str = ""
    dedup_table_name: str = ""
