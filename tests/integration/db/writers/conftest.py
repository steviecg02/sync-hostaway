"""
Shared fixtures for database writer integration tests.
"""

from __future__ import annotations

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
