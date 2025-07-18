import json
import logging
from typing import Any

from sync_hostaway.config import DEBUG
from sync_hostaway.network.auth import get_access_token
from sync_hostaway.network.client import fetch_paginated

logger = logging.getLogger(__name__)


def poll_reservations() -> list[dict[str, Any]]:
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
