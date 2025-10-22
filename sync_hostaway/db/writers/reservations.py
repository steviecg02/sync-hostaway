import json
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from sync_hostaway.config import DEBUG
from sync_hostaway.models.reservations import Reservation

logger = structlog.get_logger(__name__)


def insert_reservations(
    engine: Engine, account_id: int, data: list[dict[str, Any]], dry_run: bool = False
) -> None:
    """
    Upsert reservations into the database — only update if raw_payload has changed.

    Args:
        engine: SQLAlchemy Engine
        account_id: Hostaway Account ID
        data: List of raw Hostaway reservation payloads (dicts)
        dry_run: If True, skip DB writes and log only
    """
    now = datetime.now(tz=timezone.utc)

    from collections import Counter

    ids = [r["id"] for r in data]
    dups = [rid for rid, count in Counter(ids).items() if count > 1]
    if dups:
        logger.error("❌ Found %s duplicate reservation_id(s) in batch:", len(dups))
        for rid in dups:
            logger.error(" - reservation_id=%s, count=%s", rid, ids.count(rid))

    rows = []
    for r in data:
        reservation_id = r.get("id")
        listing_id = r.get("listingMapId")

        if not reservation_id or not account_id or not listing_id:
            logger.warning("Skipping reservation with missing id/accountId/listingMapId")
            if DEBUG:
                logger.debug(
                    "Payload with missing fields:\n%s", json.dumps(r, indent=2, default=str)
                )
            continue

        rows.append(
            {
                "id": reservation_id,
                "account_id": account_id,
                "customer_id": None,  # Optional: will populate later
                "listing_id": listing_id,
                "raw_payload": r,
                "created_at": now,
                "updated_at": now,
            }
        )

    if dry_run:
        logger.info(f"[DRY RUN] Would upsert {len(rows)} reservations")
        return

    if not rows:
        logger.info("No reservations to upsert")
        return

    if DEBUG:
        logger.info("Sample reservation to upsert:\n%s", json.dumps(rows[0], indent=2, default=str))

    with engine.begin() as conn:
        stmt = insert(Reservation).values(rows)

        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "raw_payload": insert(Reservation).excluded.raw_payload,
                "updated_at": insert(Reservation).excluded.updated_at,
            },
            where=Reservation.raw_payload.is_distinct_from(
                insert(Reservation).excluded.raw_payload
            ),
        )

        conn.execute(stmt)

    logger.info(f"Upserted {len(rows)} reservations into DB")
