import json
import logging
from typing import Any

from sync_hostaway.config import DEBUG
from sync_hostaway.network.client import fetch_paginated

logger = logging.getLogger(__name__)


def poll_listings(account_id: int) -> list[dict[str, Any]]:
    """
    Fetch raw listing data from Hostaway's /listings endpoint.

    Args:
        account_id (int): Hostaway account ID

    Returns:
        list[dict]: Raw Hostaway listing records
    """
    listings = fetch_paginated("listings", account_id=account_id)

    if DEBUG and listings:
        logger.debug("Sample listing:\n%s", json.dumps(listings[0], indent=2))

    logger.info("Fetched %d listings from Hostaway [account_id=%s]", len(listings), account_id)
    return listings
