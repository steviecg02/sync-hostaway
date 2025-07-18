import logging

from sync_hostaway.db.engine import get_engine
from sync_hostaway.db.writers.listings import insert_listings
from sync_hostaway.db.writers.messages import insert_messages
from sync_hostaway.db.writers.reservations import insert_reservations
from sync_hostaway.normalizers.messages import normalize_raw_messages
from sync_hostaway.pollers.listings import poll_listings
from sync_hostaway.pollers.messages import poll_messages
from sync_hostaway.pollers.reservations import poll_reservations

logger = logging.getLogger(__name__)


def run_sync(dry_run: bool = False) -> None:
    """
    Orchestrates full sync: pulls from all sources and writes to DB.

    Args:
        dry_run (bool): If True, data will be fetched and logged, but not written to the database.
    """
    logger.info(f"Starting full sync with dry_run={dry_run}")

    engine = get_engine()

    # Listings
    listings = poll_listings()
    insert_listings(data=listings, engine=engine, dry_run=dry_run)
    logger.info("Listings sync complete")

    # Reservations
    reservations = poll_reservations()
    insert_reservations(data=reservations, engine=engine, dry_run=dry_run)
    logger.info("Reservations sync complete")

    # Messages
    raw_conversations = poll_messages()
    normalized = normalize_raw_messages(raw_conversations)
    insert_messages(data=normalized, engine=engine, dry_run=dry_run)
    logger.info("Messages sync complete")

    logger.info("Full sync finished successfully.")
