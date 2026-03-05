"""Unit tests for SnsClient.

Exercises the SNS publish flow using unittest.mock so no real AWS calls
are made.
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from dealfinder.notifications.sns import SnsClient


class TestSnsClientPublish:
    """Tests for SnsClient.publish."""

    def test_publish_returns_message_id(self) -> None:
        """A successful publish should return the SNS MessageId."""
        mock_boto_client = MagicMock()
        mock_boto_client.publish.return_value = {"MessageId": "sns-msg-abc123"}

        with patch("dealfinder.notifications.sns.boto3.client", return_value=mock_boto_client):
            client = SnsClient(topic_arn="arn:aws:sns:us-east-1:123456789:test-topic")
            result = client.publish(subject="🔥 Deal Alert", message="50% off Sony headphones")

        assert result == "sns-msg-abc123"
        mock_boto_client.publish.assert_called_once_with(
            TopicArn="arn:aws:sns:us-east-1:123456789:test-topic",
            Subject="🔥 Deal Alert",
            Message="50% off Sony headphones",
        )

    def test_publish_truncates_subject_to_100_chars(self) -> None:
        """Subjects longer than 100 characters should be truncated."""
        mock_boto_client = MagicMock()
        mock_boto_client.publish.return_value = {"MessageId": "id"}

        with patch("dealfinder.notifications.sns.boto3.client", return_value=mock_boto_client):
            client = SnsClient(topic_arn="arn:aws:sns:us-east-1:123:topic")
            client.publish(subject="S" * 200, message="body")

        call_kwargs = mock_boto_client.publish.call_args[1]
        assert len(call_kwargs["Subject"]) <= 100

    def test_publish_raises_on_client_error(self) -> None:
        """A ClientError from boto3 should propagate to the caller."""
        mock_boto_client = MagicMock()
        mock_boto_client.publish.side_effect = ClientError(
            {"Error": {"Code": "AuthorizationError", "Message": "Not authorized"}},
            "Publish",
        )

        with patch("dealfinder.notifications.sns.boto3.client", return_value=mock_boto_client):
            client = SnsClient(topic_arn="arn:aws:sns:us-east-1:123:topic")
            with pytest.raises(ClientError):
                client.publish(subject="Alert", message="body")

    def test_client_is_lazily_initialised(self) -> None:
        """The boto3 SNS client should be created only on first access."""
        with patch("dealfinder.notifications.sns.boto3.client") as mock_factory:
            mock_factory.return_value = MagicMock()
            mock_factory.return_value.publish.return_value = {"MessageId": "x"}

            client = SnsClient(topic_arn="arn:aws:sns:us-east-1:123:topic", region="eu-west-1")
            # Client not yet created
            assert mock_factory.call_count == 0

            client.publish(subject="T", message="M")
            # Created on first publish
            mock_factory.assert_called_once_with("sns", region_name="eu-west-1")

            client.publish(subject="T2", message="M2")
            # Not created again on second call
            assert mock_factory.call_count == 1
