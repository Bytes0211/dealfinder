"""Unit tests for PushoverClient.

Exercises the HTTP messaging flow using httpx's MockTransport so no
real network calls are made.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from dealfinder.notifications.pushover import PushoverClient


class TestPushoverClientSend:
    """Tests for PushoverClient.send."""

    def test_send_returns_receipt_on_success(self) -> None:
        """A 200 response with a receipt field should be returned."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": 1, "receipt": "abc-receipt-123"}

        with patch("dealfinder.notifications.pushover.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            client = PushoverClient(api_token="test-token")
            receipt = client.send(
                user_key="user-key-123",
                title="🔥 Deal Alert",
                message="Sony headphones — 40% off",
            )

        assert receipt == "abc-receipt-123"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["data"] if "data" in call_kwargs[1] else call_kwargs[0][1]
        assert payload["token"] == "test-token"
        assert payload["user"] == "user-key-123"

    def test_send_returns_empty_receipt_when_not_in_response(self) -> None:
        """Responses without a receipt field should return empty string."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": 1}

        with patch("dealfinder.notifications.pushover.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            client = PushoverClient(api_token="test-token")
            receipt = client.send(user_key="uk", title="T", message="M")

        assert receipt == ""

    def test_send_raises_on_http_error(self) -> None:
        """A non-2xx HTTP response should propagate as HTTPStatusError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=MagicMock()
        )

        with patch("dealfinder.notifications.pushover.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            client = PushoverClient(api_token="test-token")
            with pytest.raises(httpx.HTTPStatusError):
                client.send(user_key="uk", title="T", message="M")

    def test_send_truncates_title_and_message(self) -> None:
        """Titles > 250 and messages > 1024 chars should be truncated in the payload."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"status": 1, "receipt": ""}

        with patch("dealfinder.notifications.pushover.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            client = PushoverClient(api_token="tok")
            client.send(user_key="uk", title="T" * 300, message="M" * 2000)

        payload = mock_client.post.call_args[1]["data"]
        assert len(payload["title"]) <= 250
        assert len(payload["message"]) <= 1024
