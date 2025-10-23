import json
from typing import Any

import structlog
from sqlalchemy.engine import Engine

from sync_hostaway.config import DEBUG
from sync_hostaway.db.writers._upsert import upsert_with_distinct_check
from sync_hostaway.models.listings import Listing
from sync_hostaway.utils.datetime import utc_now

logger = structlog.get_logger(__name__)


def insert_listings(
    engine: Engine, account_id: int, data: list[dict[str, Any]], dry_run: bool = False
) -> None:
    """
    Upsert listings into the database — only update if raw_payload has changed.

    Args:
        engine: SQLAlchemy Engine
        account_id: Hostaway Account ID
        data: List of raw Hostaway listing payloads (dicts)
        dry_run: If True, skip DB writes and log only
    """
    now = utc_now()
    rows = []

    for listing in data:
        listing_id = listing.get("id")

        if not listing_id or not account_id:
            logger.warning("Skipping listing with missing id or accountId")
            continue

        rows.append(
            {
                "id": listing_id,
                "account_id": account_id,
                "customer_id": None,  # Optional: will populate later
                "raw_payload": listing,
                "created_at": now,
                "updated_at": now,
            }
        )

    if dry_run:
        logger.info(f"[DRY RUN] Would upsert {len(rows)} listings")
        return

    if not rows:
        logger.info("No listings to upsert")
        return

    if DEBUG:
        logger.info(f"Sample listing to upsert {json.dumps(rows[0], default=str, indent=2)}")

    with engine.begin() as conn:
        upsert_with_distinct_check(
            conn=conn,
            table=Listing,
            rows=rows,
            conflict_column="id",
            distinct_column="raw_payload",
            update_columns=["account_id", "raw_payload", "updated_at"],
        )

    logger.info(f"Upserted {len(rows)} listings into DB")
