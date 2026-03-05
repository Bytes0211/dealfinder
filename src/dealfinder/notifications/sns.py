"""AWS SNS notification client.

Wraps the boto3 SNS ``publish`` API so the Messenger Agent can broadcast
deal alerts to all subscribers of the deal-notifications topic.
"""

import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)


class SnsClient:
    """Publish deal alert notifications to an AWS SNS topic.

    All topic subscribers (email, SMS, mobile push, etc.) receive the
    message automatically via SNS fan-out.  The boto3 SNS client is
    initialised lazily and cached on the instance for Lambda container reuse.

    Example:
        client = SnsClient(topic_arn="arn:aws:sns:us-east-1:123:dealfinder-prod-deal-notifications")
        message_id = client.publish(
            subject="🔥 Deal Alert: 40% off Sony headphones",
            message="Sony WH-1000XM5 — $179 (was $299). Shop now: https://example.com/deal",
        )
        print(message_id)  # SNS MessageId
    """

    def __init__(self, topic_arn: str, region: str = "us-east-1") -> None:
        """Initialise the SNS client.

        Args:
            topic_arn: ARN of the SNS topic to publish to.
            region: AWS region for the SNS endpoint.
        """
        self._topic_arn = topic_arn
        self._region = region
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Lazily initialise and cache the boto3 SNS client."""
        if self._client is None:
            self._client = boto3.client("sns", region_name=self._region)
        return self._client

    def publish(self, subject: str, message: str) -> str:
        """Publish a message to the SNS topic.

        Args:
            subject: Notification subject line (shown in email subscriptions,
                max 100 characters).
            message: Notification body text.

        Returns:
            SNS MessageId string.

        Raises:
            botocore.exceptions.ClientError: If the SNS API call fails.
        """
        response = self.client.publish(
            TopicArn=self._topic_arn,
            Subject=subject[:100],
            Message=message,
        )
        message_id: str = response["MessageId"]
        logger.info(f"SNS notification published to topic; MessageId={message_id}")
        return message_id
