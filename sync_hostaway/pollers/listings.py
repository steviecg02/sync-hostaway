import json
import logging

from sync_hostaway.config import DEBUG
from sync_hostaway.hostaway_api.auth import get_access_token
from sync_hostaway.hostaway_api.client import fetch_paginated

logger = logging.getLogger(__name__)


def poll_listings() -> list[dict]:
    """
    Fetch raw listing data from Hostaway's /listings endpoint.

    Returns:
        list[dict]: Raw Hostaway listing records
    """
    token = get_access_token()
    listings = fetch_paginated("listings", token)

    if DEBUG and listings:
        logger.debug("Sample listing:\n%s", json.dumps(listings[0], indent=2))

    logger.info("Fetched %d listings from Hostaway", len(listings))
    return listings
