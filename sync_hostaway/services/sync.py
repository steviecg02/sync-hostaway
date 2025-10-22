"""Account-level sync orchestrator for Hostaway integration."""

import logging

from sqlalchemy import text

from sync_hostaway.db.engine import engine
from sync_hostaway.db.writers.accounts import update_last_sync
from sync_hostaway.db.writers.listings import insert_listings
from sync_hostaway.db.writers.messages import insert_messages
from sync_hostaway.db.writers.reservations import insert_reservations
from sync_hostaway.normalizers.messages import normalize_raw_messages
from sync_hostaway.pollers.listings import poll_listings
from sync_hostaway.pollers.messages import poll_messages
from sync_hostaway.pollers.reservations import poll_reservations

logger = logging.getLogger(__name__)


def sync_account(account_id: int, dry_run: bool = False) -> None:
    """
    Sync all data for a single Hostaway account.

    Performs a full sync of listings, reservations, and messages from the
    Hostaway API and upserts them into the database.

    Args:
        account_id (int): Hostaway account ID.
        dry_run (bool): If True, skip DB writes.
    """
    logger.info("Starting sync for account_id=%s", account_id)

    # Listings
    listings = poll_listings(account_id=account_id)
    insert_listings(account_id=account_id, data=listings, engine=engine, dry_run=dry_run)

    # Reservations
    reservations = poll_reservations(account_id=account_id)
    insert_reservations(account_id=account_id, data=reservations, engine=engine, dry_run=dry_run)

    # Messages
    raw_conversations = poll_messages(account_id=account_id)
    normalized = normalize_raw_messages(raw_conversations)
    insert_messages(account_id=account_id, data=normalized, engine=engine, dry_run=dry_run)

    # Update last_sync_at timestamp if not in dry_run mode
    if not dry_run:
        with engine.begin() as conn:
            update_last_sync(conn, account_id)
        logger.info("Updated last_sync_at for account_id=%s", account_id)

    logger.info("Finished sync for account_id=%s", account_id)


def sync_all_accounts(dry_run: bool = False) -> None:
    """
    Run sync_account() for all active Hostaway accounts.

    Performs a full sync for each active account in the database.

    Args:
        dry_run (bool): If True, do not write to DB.
    """
    logger.info("Running sync for all accounts")

    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT account_id FROM hostaway.accounts
                WHERE is_active = TRUE
                ORDER BY account_id
                """
            )
        )
        account_ids = list(result.scalars().all())

    for account_id in account_ids:
        try:
            sync_account(account_id=account_id, dry_run=dry_run)
        except Exception:
            logger.exception("Sync failed for account_id=%s", account_id)

    logger.info("Completed sync_all_accounts")
