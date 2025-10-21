import logging

import requests

from sync_hostaway.db.engine import engine
from sync_hostaway.db.readers.accounts import get_account_credentials
from sync_hostaway.db.writers.accounts import update_access_token

logger = logging.getLogger(__name__)
TOKEN_URL = "https://api.hostaway.com/v1/accessTokens"


def create_access_token(client_id: str, client_secret: str) -> str:
    """
    Exchange client ID and secret for a Hostaway access token.

    Args:
        client_id (str): Hostaway account ID as a string.
        client_secret (str): Hostaway API secret.

    Returns:
        str: Bearer access token.
    """
    logger.info("Requesting new Hostaway access token for account_id=%s", client_id)

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "general",
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache",
    }

    try:
        response = requests.post(TOKEN_URL, data=payload, headers=headers)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Token request failed: %s", e)
        logger.error("Status Code: %s", getattr(response, "status_code", "N/A"))
        logger.error("Response Text: %s", getattr(response, "text", "N/A"))
        raise

    token = response.json().get("access_token")
    if not isinstance(token, str):
        logger.error("Access token missing in response: %s", response.text)
        raise RuntimeError("No access_token in Hostaway response.")

    return token


def refresh_access_token(account_id: int) -> str:
    """
    Refresh and store a new Hostaway access token for the given account.

    Args:
        account_id (int): Hostaway account ID.

    Returns:
        str: New bearer token.
    """
    with engine.begin() as conn:
        creds = get_account_credentials(conn, account_id)
        if not creds or not creds.get("client_secret"):
            raise RuntimeError(f"No valid Hostaway credentials found for account_id={account_id}")

        new_token = create_access_token(str(account_id), creds["client_secret"])
        update_access_token(conn, account_id, new_token)

    logger.info("Refreshed Hostaway access token for account_id=%s", account_id)
    return new_token


def get_access_token(account_id: int) -> str:
    """
    Get the current valid Hostaway access token from the DB.
    Refreshes if missing.

    Args:
        account_id (int): Hostaway account ID.

    Returns:
        str: Access token
    """
    with engine.connect() as conn:
        creds = get_account_credentials(conn, account_id)

    token = creds.get("access_token") if creds else None
    if token and isinstance(token, str):
        return token

    return refresh_access_token(account_id)


def get_or_refresh_token(account_id: int, prev_token: str | None = None) -> str:
    """
    Get the token from DB. If it's missing or matches a failed token, refresh it.

    Args:
        account_id (int): Hostaway account ID
        prev_token (str | None): Optional token that just failed

    Returns:
        str: Valid bearer token
    """
    token = get_access_token(account_id)

    if not token:
        logger.debug("No token found for account_id=%s; refreshing", account_id)
        return refresh_access_token(account_id)

    if prev_token is not None and token == prev_token:
        logger.debug("Token matched failed prev_token for account_id=%s; refreshing", account_id)
        return refresh_access_token(account_id)

    logger.debug("Using valid cached token for account_id=%s", account_id)
    return token
