"""Agent configuration for Deal Finder Lambda functions.

Reads all settings from environment variables with the DEALFINDER_ prefix,
with sensible defaults suitable for local development.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """Configuration for Lambda agent functions.

    Attributes:
        discount_threshold: Minimum discount percentage to flag a deal as high value.
        bedrock_region: AWS region used for Bedrock API calls.
        bedrock_model_id: Bedrock model identifier for Claude (Evaluator).
        notification_queue_url: SQS URL for the notification-dispatch queue.
        sns_topic_arn: SNS topic ARN for deal-notification fan-out.
        ses_sender_email: Verified SES sender address for email notifications.
        pushover_api_token: Pushover application token (SecretStr; from Secrets Manager).
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
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    notification_queue_url: str = ""

    # Messenger Agent fields
    sns_topic_arn: str = ""
    ses_sender_email: str = ""
    pushover_api_token: SecretStr = SecretStr("")
    dedup_table_name: str = ""
