import logging

import requests

from sync_hostaway.config import HOSTAWAY_ACCESS_TOKEN, HOSTAWAY_CLIENT_ID, HOSTAWAY_CLIENT_SECRET

logger = logging.getLogger(__name__)
TOKEN_URL = "https://api.hostaway.com/v1/accessTokens"


def get_access_token() -> str:
    """
    Returns a Hostaway API access token.
    Phase 1: Uses static env-based config. Will be replaced with DB lookup.

    Returns:
        str: Bearer token string
    """
    if HOSTAWAY_ACCESS_TOKEN:
        logger.debug("Using static access token from config.")
        return HOSTAWAY_ACCESS_TOKEN

    if HOSTAWAY_CLIENT_ID and HOSTAWAY_CLIENT_SECRET:
        logger.info("Requesting access token using client credentials.")
        res = requests.post(
            TOKEN_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": HOSTAWAY_CLIENT_ID,
                "client_secret": HOSTAWAY_CLIENT_SECRET,
            },
        )
        res.raise_for_status()
        token = res.json().get("access_token")
        if not token:
            raise RuntimeError("No access_token in Hostaway response.")
        return token

    raise RuntimeError("Missing HOSTAWAY_ACCESS_TOKEN or client credentials.")
