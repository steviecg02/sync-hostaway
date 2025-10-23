"""
Shared fixtures for database writer integration tests.
"""

from __future__ import annotations

import json
from typing import Any, Generator

import pytest
from sqlalchemy import text

from sync_hostaway.db.engine import engine


@pytest.fixture
def test_account(request: Any) -> Generator[int, None, None]:
    """
    Create a test account for database writer tests.

    Returns the account_id. Cleans up after test completes.
    """
    # Get account_id from test parameter or use unique default
    account_id = getattr(request, "param", 99999)

    # Create test account
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO hostaway.accounts (account_id, client_secret, is_active)
                VALUES (:account_id, 'test-secret', true)
                ON CONFLICT (account_id) DO NOTHING
                """
            ),
            {"account_id": account_id},
        )

    yield account_id

    # Cleanup: Delete all related data
    with engine.begin() as conn:
        # Delete in correct order to respect foreign keys
        conn.execute(
            text("DELETE FROM hostaway.messages WHERE account_id = :account_id"),
            {"account_id": account_id},
        )
        conn.execute(
            text("DELETE FROM hostaway.reservations WHERE account_id = :account_id"),
            {"account_id": account_id},
        )
        conn.execute(
            text("DELETE FROM hostaway.listings WHERE account_id = :account_id"),
            {"account_id": account_id},
        )
        conn.execute(
            text("DELETE FROM hostaway.accounts WHERE account_id = :account_id"),
            {"account_id": account_id},
        )


@pytest.fixture
def test_account_with_listing(test_account: int) -> Generator[tuple[int, int], None, None]:
    """
    Create a test account with a test listing for reservation tests.

    Returns tuple of (account_id, listing_id).
    """
    account_id = test_account
    listing_id = 999999  # Fixed test listing ID

    # Create test listing
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO hostaway.listings (id, account_id, raw_payload, created_at, updated_at)
                VALUES (:id, :account_id, CAST(:payload AS jsonb), NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": listing_id,
                "account_id": account_id,
                "payload": json.dumps({"id": 999999, "name": "Test Listing"}),
            },
        )

    yield (account_id, listing_id)

    # Cleanup handled by test_account fixture


@pytest.fixture
def test_account_with_reservation(
    test_account_with_listing: tuple[int, int],
) -> Generator[tuple[int, int], None, None]:
    """
    Create a test account with listing and reservation for message tests.

    Returns tuple of (account_id, reservation_id).
    """
    account_id, listing_id = test_account_with_listing
    reservation_id = 888888  # Fixed test reservation ID

    # Create test reservation
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO hostaway.reservations
                (id, account_id, listing_id, raw_payload, created_at, updated_at)
                VALUES (:id, :account_id, :listing_id, CAST(:payload AS jsonb), NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": reservation_id,
                "account_id": account_id,
                "listing_id": listing_id,
                "payload": json.dumps({"id": 888888, "guestName": "Test Guest"}),
            },
        )

    yield (account_id, reservation_id)

    # Cleanup handled by test_account fixture
