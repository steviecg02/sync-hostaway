import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine

from sync_hostaway.config import DEBUG
from sync_hostaway.models.accounts import Account

logger = logging.getLogger(__name__)


def insert_accounts(engine: Engine, data: list[dict[str, Any]], dry_run: bool = False) -> None:
    """
    Upsert accounts into the database — only update if values changed.

    Args:
        engine (Engine): SQLAlchemy engine to open a transaction.
        data (list[dict[str, Any]]): Account rows to insert.
        dry_run (bool): If True, skip DB writes and log only.
    """
    now = datetime.utcnow()
    rows: list[dict[str, Any]] = []

    for acct in data:
        account_id = acct.get("account_id")
        if account_id is None:
            logger.warning("Skipping account with missing account_id")
            continue

        rows.append(
            {
                "account_id": account_id,
                "customer_id": acct.get("customer_id"),
                "client_secret": acct.get("client_secret"),
                "access_token": acct.get("access_token"),
                "webhook_id": acct.get("webhook_id"),
                "is_active": acct.get("is_active", True),
                "created_at": now,
                "updated_at": now,
            }
        )

    if not rows:
        logger.info("No accounts to upsert")
        return

    if dry_run:
        logger.info(f"[DRY RUN] Would upsert {len(rows)} accounts")
        return

    if DEBUG:
        logger.info(f"Sample account to upsert:\n{json.dumps(rows[0], default=str, indent=2)}")

    stmt = (
        insert(Account)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["account_id"],
            set_={
                "customer_id": insert(Account).excluded.customer_id,
                "client_secret": insert(Account).excluded.client_secret,
                "access_token": insert(Account).excluded.access_token,
                "webhook_id": insert(Account).excluded.webhook_id,
                "is_active": insert(Account).excluded.is_active,
                "updated_at": insert(Account).excluded.updated_at,
            },
            where=(
                Account.customer_id.is_distinct_from(insert(Account).excluded.customer_id)
                | Account.client_secret.is_distinct_from(insert(Account).excluded.client_secret)
                | Account.access_token.is_distinct_from(insert(Account).excluded.access_token)
                | Account.webhook_id.is_distinct_from(insert(Account).excluded.webhook_id)
                | Account.is_active.is_distinct_from(insert(Account).excluded.is_active)
            ),
        )
    )

    with engine.begin() as conn:
        conn.execute(stmt)

    logger.info(f"Upserted {len(rows)} accounts into DB")


def update_access_token(conn: Connection, account_id: int, token: str) -> None:
    """
    Upsert only the access_token for an existing account.

    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.
        token (str): New bearer token to save.
    """
    now = datetime.utcnow()

    stmt = insert(Account).values(
        [
            {
                "account_id": account_id,
                "access_token": token,
                "updated_at": now,
            }
        ]
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=["account_id"],
        set_={
            "access_token": stmt.excluded.access_token,
            "updated_at": stmt.excluded.updated_at,
        },
        where=Account.access_token.is_distinct_from(stmt.excluded.access_token),
    )

    conn.execute(stmt)


def update_account(conn: Connection, account_id: int, data: dict[str, Any]) -> None:
    """
    Update account fields for an existing account.

    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.
        data (dict): Fields to update (only non-None values)
    """
    from sqlalchemy import update

    now = datetime.utcnow()
    data["updated_at"] = now

    stmt = update(Account).where(Account.account_id == account_id).values(**data)

    conn.execute(stmt)


def soft_delete_account(conn: Connection, account_id: int) -> None:
    """
    Soft delete an account by setting is_active to False.

    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.
    """
    from sqlalchemy import update

    now = datetime.utcnow()

    stmt = (
        update(Account)
        .where(Account.account_id == account_id)
        .values(is_active=False, updated_at=now)
    )

    conn.execute(stmt)


def hard_delete_account(conn: Connection, account_id: int) -> None:
    """
    Permanently delete an account from the database.

    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.
    """
    from sqlalchemy import delete

    stmt = delete(Account).where(Account.account_id == account_id)
    conn.execute(stmt)


def update_last_sync(conn: Connection, account_id: int) -> None:
    """
    Update the last_sync_at timestamp for an account.

    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.
    """
    from sqlalchemy import update

    now = datetime.utcnow()

    stmt = (
        update(Account)
        .where(Account.account_id == account_id)
        .values(last_sync_at=now, updated_at=now)
    )

    conn.execute(stmt)


def update_webhook_id(conn: Connection, account_id: int, webhook_id: int) -> None:
    """
    Update the webhook_id for an account after webhook registration.

    Args:
        conn (Connection): SQLAlchemy DB connection.
        account_id (int): Hostaway account ID.
        webhook_id (int): Webhook ID from Hostaway API.
    """
    from sqlalchemy import update

    now = datetime.utcnow()

    stmt = (
        update(Account)
        .where(Account.account_id == account_id)
        .values(webhook_id=webhook_id, updated_at=now)
    )

    conn.execute(stmt)

    logger.info("Updated webhook_id=%s for account_id=%s", webhook_id, account_id)
