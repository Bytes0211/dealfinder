"""AWS SES email notification client.

Wraps the boto3 SES v2 ``send_email`` API so the Messenger Agent can
dispatch deal alert emails through a verified SES sender address.
"""

import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)


class SesClient:
    """Send transactional emails via AWS Simple Email Service (v2).

    The boto3 SES client is initialised lazily and cached on the
    instance, which is safe for Lambda container reuse.

    Example:
        client = SesClient(sender_email="deals@example.com", region="us-east-1")
        msg_id = client.send_email(
            to_address="user@example.com",
            subject="🔥 Deal Alert: 40% off Sony headphones",
            body_text="Visit https://example.com/deal for details.",
        )
        print(msg_id)  # SES message ID
    """

    def __init__(self, sender_email: str, region: str = "us-east-1") -> None:
        """Initialise the SES email client.

        Args:
            sender_email: Verified SES sender address (From:).
            region: AWS region for the SES endpoint.
        """
        self._sender = sender_email
        self._region = region
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Lazily initialise the boto3 SES v2 client."""
        if self._client is None:
            self._client = boto3.client("sesv2", region_name=self._region)
        return self._client

    def send_email(self, to_address: str, subject: str, body_text: str) -> str:
        """Send a plain-text email via SES.

        Args:
            to_address: Recipient email address.
            subject: Email subject line.
            body_text: Plain-text email body.

        Returns:
            SES MessageId string.

        Raises:
            botocore.exceptions.ClientError: If the SES API call fails.
        """
        response = self.client.send_email(
            FromEmailAddress=self._sender,
            Destination={"ToAddresses": [to_address]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
                }
            },
        )
        message_id: str = response["MessageId"]
        logger.info(f"SES email sent to {to_address}; MessageId={message_id}")
        return message_id
