import json
import logging
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from sync_hostaway.config import DEBUG
from sync_hostaway.models.messages import MessageThread

logger = logging.getLogger(__name__)


def insert_messages(engine: Engine, data: list[dict[str, Any]], dry_run: bool = False) -> None:
    """
    Upsert normalized messages into the database.
    Only updates if the messages field has changed.

    Args:
        engine: SQLAlchemy Engine
        data: List of normalized message thread dicts (one per reservation)
        dry_run: If True, skip DB writes and log only
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would upsert {len(data)} message threads")
        return

    if not data:
        logger.info("No message threads to upsert")
        return

    if DEBUG:
        logger.info(f"Sample message thread to upsert {json.dumps(data[0], default=str, indent=2)}")

    with engine.begin() as conn:
        stmt = insert(MessageThread).values(data)

        stmt = stmt.on_conflict_do_update(
            index_elements=["reservation_id"],
            set_={
                "raw_messages": insert(MessageThread).excluded.raw_messages,
                "updated_at": insert(MessageThread).excluded.updated_at,
            },
            where=MessageThread.raw_messages.is_distinct_from(
                insert(MessageThread).excluded.raw_messages
            ),
        )

        conn.execute(stmt)

    logger.info(f"Upserted {len(data)} message threads into DB")
