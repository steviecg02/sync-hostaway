import json
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from sync_hostaway.config import DEBUG
from sync_hostaway.models.listings import Listing

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
    now = datetime.utcnow()
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
        stmt = insert(Listing).values(rows)

        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "account_id": insert(Listing).excluded.account_id,
                "raw_payload": insert(Listing).excluded.raw_payload,
                "updated_at": insert(Listing).excluded.updated_at,
            },
            where=Listing.raw_payload.is_distinct_from(insert(Listing).excluded.raw_payload),
        )

        conn.execute(stmt)

    logger.info(f"Upserted {len(rows)} listings into DB")
