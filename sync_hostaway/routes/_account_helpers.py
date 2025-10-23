"""
Internal helper functions for account route handlers.

This module contains validation and utility functions to reduce duplication
and improve readability in the main route handlers.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.engine import Connection

from sync_hostaway.db.readers.accounts import account_exists


def validate_account_exists_or_404(conn: Connection, account_id: int) -> None:
    """
    Validate that an account exists, raise 404 if not.

    Args:
        conn: Database connection
        account_id: Account ID to check

    Raises:
        HTTPException: 404 if account doesn't exist
    """
    if not account_exists(conn, account_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found",
        )


def validate_account_not_exists_or_422(conn: Connection, account_id: int) -> None:
    """
    Validate that an account does NOT exist, raise 422 if it does.

    Args:
        conn: Database connection
        account_id: Account ID to check

    Raises:
        HTTPException: 422 if account already exists
    """
    if account_exists(conn, account_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Account {account_id} already exists",
        )


def validate_client_secret_or_400(client_secret: str | None) -> None:
    """
    Validate that client_secret is provided, raise 400 if not.

    Args:
        client_secret: Client secret to validate

    Raises:
        HTTPException: 400 if client_secret is None or empty
    """
    if not client_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client secret is required",
        )


def should_trigger_sync_on_update(
    account_info: dict[str, Any],
    update_data: dict[str, Any],
) -> bool:
    """
    Determine if sync should be triggered based on update changes.

    Sync is triggered when:
    1. Client secret is being changed, AND
    2. Account has never been synced before

    Args:
        account_info: Current account information from database
        update_data: Fields being updated

    Returns:
        bool: True if sync should be triggered, False otherwise
    """
    client_secret_changed = "client_secret" in update_data and update_data[
        "client_secret"
    ] != account_info.get("client_secret")
    never_synced = account_info.get("last_sync_at") is None

    return client_secret_changed and never_synced
