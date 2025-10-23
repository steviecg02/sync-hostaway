import json
from typing import Any

import structlog

from sync_hostaway.config import DEBUG
from sync_hostaway.metrics import poll_duration, poll_total, records_synced
from sync_hostaway.network.client import fetch_paginated

logger = structlog.get_logger(__name__)


def poll_listings(account_id: int) -> list[dict[str, Any]]:
    """
    Fetch raw listing data from Hostaway's /listings endpoint.

    Args:
        account_id (int): Hostaway account ID

    Returns:
        list[dict]: Raw Hostaway listing records
    """
    with poll_duration.labels(account_id=str(account_id), entity_type="listings").time():
        try:
            listings = fetch_paginated("listings", account_id=account_id)

            if DEBUG and listings:
                logger.debug("Sample listing:\n%s", json.dumps(listings[0], indent=2))

            logger.info(
                "Fetched %d listings from Hostaway [account_id=%s]", len(listings), account_id
            )

            # Record metrics
            records_synced.labels(account_id=str(account_id), entity_type="listings").inc(
                len(listings)
            )
            poll_total.labels(
                account_id=str(account_id), entity_type="listings", status="success"
            ).inc()

            return listings
        except Exception:
            poll_total.labels(
                account_id=str(account_id), entity_type="listings", status="failure"
            ).inc()
            raise
