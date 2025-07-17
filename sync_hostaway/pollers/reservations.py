import json
import logging

from sync_hostaway.config import DEBUG
from sync_hostaway.hostaway_api.auth import get_access_token
from sync_hostaway.hostaway_api.client import fetch_paginated

logger = logging.getLogger(__name__)


def poll_reservations() -> list[dict]:
    """
    Fetch raw reservation data from Hostaway's /reservations endpoint.

    Returns:
        list[dict]: Raw Hostaway reservation records
    """
    token = get_access_token()
    reservations = fetch_paginated("reservations", token)

    if DEBUG and reservations:
        logger.debug("Sample reservation:\n%s", json.dumps(reservations[0], indent=2))

    logger.info("Fetched %d reservations from Hostaway", len(reservations))
    return reservations
