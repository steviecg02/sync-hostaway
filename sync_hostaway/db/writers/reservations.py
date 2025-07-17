import json
import logging
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from sync_hostaway.config import DEBUG
from sync_hostaway.models.reservations import Reservation

logger = logging.getLogger(__name__)


def insert_reservations(engine: Engine, data: list[dict], dry_run: bool = False) -> None:
    """
    Upsert reservations into the database.

    Args:
        engine: SQLAlchemy Engine
        data: List of raw Hostaway reservation payloads (dicts)
        dry_run: If True, skip DB writes and log only
    """
    now = datetime.utcnow()

    rows = []
    for reservation in data:
        reservation_id = reservation.get("id")
        if not reservation_id:
            logger.warning("Skipping reservation without ID")
            continue

        rows.append(
            {
                "id": reservation_id,
                "listing_id": reservation["listingMapId"],
                "raw_payload": reservation,
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
        logger.info(f"Sample reservation to upsert {json.dumps(rows[0], default=str, indent=2)}")

    with engine.begin() as cur:
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

        cur.execute(stmt)

    logger.info(f"Upserted {len(rows)} reservations into DB")
