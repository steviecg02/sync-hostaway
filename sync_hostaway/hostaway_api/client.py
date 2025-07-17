import logging
import time
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hostaway.com/v1/"


def fetch_paginated(endpoint: str, token: str, limit: int = 100) -> list[dict]:
    """
    Fetches all pages of a paginated Hostaway API endpoint.

    Args:
        endpoint (str): e.g. 'listings'
        token (str): Bearer token

    Returns:
        list[dict]: Combined result list
    """
    results = []
    offset = 0
    page = 0

    while True:
        url = urljoin(BASE_URL, endpoint)
        headers = {"Authorization": f"Bearer {token}"}
        params = {"limit": limit, "offset": offset}
        res = requests.get(url, headers=headers, params=params)

        if res.status_code == 429:
            delay = min(60, 2**page)
            logger.warning("Rate limited on %s. Retrying in %s seconds...", endpoint, delay)
            time.sleep(delay)
            continue

        res.raise_for_status()
        data = res.json().get("result", [])
        logger.info("Fetched %d from %s (offset=%d)", len(data), endpoint, offset)

        results.extend(data)
        if len(data) < limit:
            break

        offset += limit
        page += 1

    return results
