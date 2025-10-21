import json
import logging
from typing import Any

from sync_hostaway.config import DEBUG
from sync_hostaway.network.client import fetch_paginated

logger = logging.getLogger(__name__)


def poll_reservations(account_id: int) -> list[dict[str, Any]]:
    """
    Fetch raw reservation data from Hostaway's /reservations endpoint.

    Args:
        account_id (int): Hostaway account ID

    Returns:
        list[dict]: Raw Hostaway reservation records
    """
    reservations = fetch_paginated("reservations", account_id=account_id)

    if DEBUG and reservations:
        logger.debug("Sample reservation:\n%s", json.dumps(reservations[0], indent=2))

    logger.info(
        "Fetched %d reservations from Hostaway [account_id=%d]", len(reservations), account_id
    )
    return reservations
