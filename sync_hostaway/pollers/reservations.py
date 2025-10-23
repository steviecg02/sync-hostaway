import json
from typing import Any

import structlog

from sync_hostaway.config import DEBUG
from sync_hostaway.metrics import poll_duration, poll_total, records_synced
from sync_hostaway.network.client import fetch_paginated

logger = structlog.get_logger(__name__)


def poll_reservations(account_id: int) -> list[dict[str, Any]]:
    """
    Fetch raw reservation data from Hostaway's /reservations endpoint.

    Args:
        account_id (int): Hostaway account ID

    Returns:
        list[dict]: Raw Hostaway reservation records
    """
    with poll_duration.labels(account_id=str(account_id), entity_type="reservations").time():
        try:
            reservations = fetch_paginated("reservations", account_id=account_id)

            if DEBUG and reservations:
                logger.debug("Sample reservation:\n%s", json.dumps(reservations[0], indent=2))

            logger.info(
                "Fetched %d reservations from Hostaway [account_id=%d]",
                len(reservations),
                account_id,
            )

            # Record metrics
            records_synced.labels(account_id=str(account_id), entity_type="reservations").inc(
                len(reservations)
            )
            poll_total.labels(
                account_id=str(account_id), entity_type="reservations", status="success"
            ).inc()

            return reservations
        except Exception:
            poll_total.labels(
                account_id=str(account_id), entity_type="reservations", status="failure"
            ).inc()
            raise
