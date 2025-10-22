"""Account-level sync orchestrator for Hostaway integration."""

import structlog
from sqlalchemy import text

from sync_hostaway.db.engine import engine
from sync_hostaway.db.writers.accounts import update_last_sync, update_webhook_id
from sync_hostaway.db.writers.listings import insert_listings
from sync_hostaway.db.writers.messages import insert_messages
from sync_hostaway.db.writers.reservations import insert_reservations
from sync_hostaway.normalizers.messages import normalize_raw_messages
from sync_hostaway.pollers.listings import poll_listings
from sync_hostaway.pollers.messages import poll_messages
from sync_hostaway.pollers.reservations import poll_reservations
from sync_hostaway.services.webhook_registration import register_webhook

logger = structlog.get_logger(__name__)


def sync_account(account_id: int, dry_run: bool = False) -> None:
    """
    Sync all data for a single Hostaway account.

    Performs a full sync of listings, reservations, and messages from the
    Hostaway API and upserts them into the database.

    Args:
        account_id (int): Hostaway account ID.
        dry_run (bool): If True, skip DB writes.
    """
    logger.info("sync_started", account_id=account_id)

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
        logger.info("last_sync_updated", account_id=account_id)

        # Register webhook with Hostaway after initial sync completes
        # This enables real-time event notifications for new reservations and messages
        try:
            webhook_id = register_webhook(account_id)
            if webhook_id:
                with engine.begin() as conn:
                    update_webhook_id(conn, account_id, webhook_id)
                logger.info(
                    "webhook_registered",
                    account_id=account_id,
                    webhook_id=webhook_id,
                )
            else:
                logger.warning(
                    "webhook_registration_no_id",
                    account_id=account_id,
                )
        except Exception as e:
            logger.exception(
                "webhook_registration_failed",
                account_id=account_id,
                error=str(e),
            )

    logger.info(
        "sync_completed",
        account_id=account_id,
        listings_count=len(listings),
        reservations_count=len(reservations),
        messages_count=len(normalized),
    )


def sync_all_accounts(dry_run: bool = False) -> None:
    """
    Run sync_account() for all active Hostaway accounts.

    Performs a full sync for each active account in the database.

    Args:
        dry_run (bool): If True, do not write to DB.
    """
    logger.info("sync_all_accounts_started")

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

    logger.info("active_accounts_found", count=len(account_ids))

    for account_id in account_ids:
        try:
            sync_account(account_id=account_id, dry_run=dry_run)
        except Exception as e:
            logger.exception("account_sync_failed", account_id=account_id, error=str(e))

    logger.info("sync_all_accounts_completed", total_accounts=len(account_ids))
