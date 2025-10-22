"""
Hostaway webhook registration service.

Automatically registers webhooks with Hostaway after account sync completes.
"""

import logging
from typing import Any

import requests

from sync_hostaway.config import WEBHOOK_BASE_URL
from sync_hostaway.network.auth import get_or_refresh_token

logger = logging.getLogger(__name__)

# Hostaway API base URL
HOSTAWAY_API_BASE_URL = "https://api.hostaway.com/v1"


def register_webhook(account_id: int) -> int | None:
    """
    Register a unified webhook with Hostaway for the given account.

    This is called after the initial account sync completes to enable
    real-time event notifications for reservations and messages.

    Args:
        account_id: Hostaway account ID

    Returns:
        int | None: Webhook ID from Hostaway if successful, None if failed

    Raises:
        requests.HTTPError: If API call fails after retries
    """
    token = get_or_refresh_token(account_id)
    webhook_url = f"{WEBHOOK_BASE_URL}/hostaway/webhooks"

    payload = {
        "isEnabled": 1,
        "url": webhook_url,
        "login": None,  # We use HTTP Basic Auth, not per-webhook credentials
        "password": None,
        "alertingEmailAddress": None,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }

    try:
        logger.info(
            "Registering webhook for account %s: url=%s",
            account_id,
            webhook_url,
        )

        response = requests.post(
            f"{HOSTAWAY_API_BASE_URL}/webhooks/unifiedWebhooks",
            json=payload,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        result: dict[str, Any] = response.json()
        webhook_id = result.get("result", {}).get("id")

        if webhook_id:
            logger.info(
                "Webhook registered successfully: account=%s, webhook_id=%s",
                account_id,
                webhook_id,
            )
            return int(webhook_id)
        else:
            logger.error(
                "Webhook registration returned no ID: account=%s, response=%s",
                account_id,
                result,
            )
            return None

    except requests.HTTPError as e:
        logger.error(
            "Failed to register webhook: account=%s, status=%s, response=%s",
            account_id,
            e.response.status_code if e.response else "N/A",
            e.response.text if e.response else "N/A",
        )
        raise

    except Exception as e:
        logger.exception(
            "Unexpected error registering webhook: account=%s, error=%s",
            account_id,
            str(e),
        )
        raise


def delete_webhook(account_id: int, webhook_id: int) -> bool:
    """
    Delete a webhook registration from Hostaway.

    This should be called when an account is hard deleted to clean up
    the webhook registration.

    Args:
        account_id: Hostaway account ID
        webhook_id: Webhook ID from Hostaway

    Returns:
        bool: True if successfully deleted, False otherwise
    """
    try:
        token = get_or_refresh_token(account_id)

        headers = {
            "Authorization": f"Bearer {token}",
            "Cache-Control": "no-cache",
        }

        response = requests.delete(
            f"{HOSTAWAY_API_BASE_URL}/webhooks/unifiedWebhooks/{webhook_id}",
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        logger.info(
            "Webhook deleted successfully: account=%s, webhook_id=%s",
            account_id,
            webhook_id,
        )
        return True

    except requests.HTTPError as e:
        logger.error(
            "Failed to delete webhook: account=%s, webhook_id=%s, status=%s",
            account_id,
            webhook_id,
            e.response.status_code if e.response else "N/A",
        )
        return False

    except Exception as e:
        logger.exception(
            "Unexpected error deleting webhook: account=%s, webhook_id=%s, error=%s",
            account_id,
            webhook_id,
            str(e),
        )
        return False
