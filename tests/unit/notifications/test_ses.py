"""Unit tests for SesClient.

Uses unittest.mock to intercept boto3 SES v2 calls without real AWS credentials.
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from dealfinder.notifications.ses import SesClient


class TestSesClientSendEmail:
    """Tests for SesClient.send_email."""

    def test_send_email_returns_message_id(self) -> None:
        """A successful SES send should return the MessageId."""
        mock_boto_client = MagicMock()
        mock_boto_client.send_email.return_value = {"MessageId": "ses-msg-id-001"}

        with patch("dealfinder.notifications.ses.boto3.client", return_value=mock_boto_client):
            client = SesClient(sender_email="deals@example.com", region="us-east-1")
            msg_id = client.send_email(
                to_address="user@example.com",
                subject="🔥 40% off Sony headphones",
                body_text="Visit https://example.com/deal",
            )

        assert msg_id == "ses-msg-id-001"
        mock_boto_client.send_email.assert_called_once()
        call_kwargs = mock_boto_client.send_email.call_args[1]
        assert call_kwargs["FromEmailAddress"] == "deals@example.com"
        assert call_kwargs["Destination"]["ToAddresses"] == ["user@example.com"]

    def test_send_email_raises_on_client_error(self) -> None:
        """A boto3 ClientError from SES should propagate to the caller."""
        mock_boto_client = MagicMock()
        mock_boto_client.send_email.side_effect = ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "Email address not verified"}},
            "SendEmail",
        )

        with patch("dealfinder.notifications.ses.boto3.client", return_value=mock_boto_client):
            client = SesClient(sender_email="deals@example.com")
            with pytest.raises(ClientError):
                client.send_email(
                    to_address="bad@example.com",
                    subject="Test",
                    body_text="Test body",
                )

    def test_client_lazy_initialisation(self) -> None:
        """The boto3 client should be created only on first use."""
        with patch("dealfinder.notifications.ses.boto3.client") as mock_factory:
            mock_factory.return_value = MagicMock()
            mock_factory.return_value.send_email.return_value = {"MessageId": "id-1"}

            ses = SesClient(sender_email="a@b.com", region="eu-west-1")
            # No boto3 call yet
            mock_factory.assert_not_called()

            # First access creates client
            ses.send_email("to@b.com", "S", "B")
            mock_factory.assert_called_once_with("sesv2", region_name="eu-west-1")

            # Second call reuses same client
            ses.send_email("to@b.com", "S2", "B2")
            mock_factory.assert_called_once()  # still only one call

    def test_send_email_formats_subject_correctly(self) -> None:
        """Subject and body should be wrapped in the SES Simple content structure."""
        mock_boto_client = MagicMock()
        mock_boto_client.send_email.return_value = {"MessageId": "x"}

        with patch("dealfinder.notifications.ses.boto3.client", return_value=mock_boto_client):
            client = SesClient(sender_email="from@x.com")
            client.send_email("to@x.com", "My Subject", "My Body")

        content = mock_boto_client.send_email.call_args[1]["Content"]
        assert content["Simple"]["Subject"]["Data"] == "My Subject"
        assert content["Simple"]["Body"]["Text"]["Data"] == "My Body"
