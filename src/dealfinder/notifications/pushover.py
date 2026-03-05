"""Pushover push notification client.

Wraps the Pushover Messages API so the Messenger Agent can send
deal alerts to users who have a Pushover account configured.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
_PUSHOVER_TIMEOUT_SECONDS = 10


class PushoverClient:
    """Send push notifications via the Pushover Messages API.

    The client holds the application API token and creates a new
    ``httpx.Client`` per call so it is safe to share across threads.

    Example:
        client = PushoverClient(api_token="apptoken")
        receipt = client.send(
            user_key="userkey",
            title="🔥 Deal Alert",
            message="Sony headphones — 40% off",
        )
        print(receipt)  # "receipt-id-from-pushover"
    """

    def __init__(self, api_token: str) -> None:
        """Initialise the Pushover client.

        Args:
            api_token: Pushover application API token.
        """
        self._api_token = api_token

    def send(self, user_key: str, title: str, message: str) -> str:
        """Send a push notification to a Pushover user.

        Args:
            user_key: The recipient's Pushover user or group key.
            title: Notification title (max 250 characters).
            message: Notification body (max 1024 characters).

        Returns:
            The ``receipt`` field from the Pushover response, or an empty
            string for non-emergency priority messages that don't include one.

        Raises:
            httpx.HTTPStatusError: If the Pushover API returns a non-2xx status.
            httpx.RequestError: On network-level errors.
        """
        payload = {
            "token": self._api_token,
            "user": user_key,
            "title": title[:250],
            "message": message[:1024],
        }

        with httpx.Client(timeout=_PUSHOVER_TIMEOUT_SECONDS) as client:
            response = client.post(_PUSHOVER_API_URL, data=payload)
            response.raise_for_status()

        body = response.json()
        receipt = body.get("receipt", "")
        logger.info(f"Pushover notification sent to user {user_key[:8]}…; receipt={receipt!r}")
        return receipt
