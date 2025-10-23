"""
Integration tests for messages database writer.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from sync_hostaway.db.engine import engine
from sync_hostaway.db.writers.messages import insert_messages
from sync_hostaway.models.messages import MessageThread


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [77777], indirect=True)
def test_insert_messages_creates_new_threads(
    test_account_with_reservation: tuple[int, int],
) -> None:
    """Test that insert_messages creates new message thread records."""
    account_id, reservation_id = test_account_with_reservation
    data = [
        {
            "reservation_id": reservation_id,
            "raw_messages": [
                {"id": 1, "message": "Hello", "sent_at": "2024-01-01T10:00:00Z"},
                {"id": 2, "message": "Hi there", "sent_at": "2024-01-01T10:05:00Z"},
            ],
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T10:05:00Z",
        },
    ]

    insert_messages(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(
            select(MessageThread)
            .where(MessageThread.account_id == account_id)
            .order_by(MessageThread.reservation_id)
        ).fetchall()

        assert len(result) == 1
        assert result[0].reservation_id == reservation_id
        assert result[0].account_id == account_id
        assert len(result[0].raw_messages) == 2
        assert result[0].raw_messages[0]["message"] == "Hello"


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [77776], indirect=True)
def test_insert_messages_updates_existing_threads_when_messages_change(
    test_account_with_reservation: tuple[int, int],
) -> None:
    """Test that insert_messages updates existing threads when raw_messages changes."""
    account_id, reservation_id = test_account_with_reservation

    # Insert initial thread
    initial_data = [
        {
            "reservation_id": reservation_id,
            "raw_messages": [
                {"id": 10, "message": "Original message", "sent_at": "2024-01-01T10:00:00Z"},
            ],
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T10:00:00Z",
        }
    ]
    insert_messages(engine, account_id, initial_data)

    # Update with new messages
    updated_data = [
        {
            "reservation_id": reservation_id,
            "raw_messages": [
                {"id": 10, "message": "Original message", "sent_at": "2024-01-01T10:00:00Z"},
                {"id": 11, "message": "New message", "sent_at": "2024-01-01T11:00:00Z"},
            ],
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T11:00:00Z",
        }
    ]
    insert_messages(engine, account_id, updated_data)

    with engine.connect() as conn:
        result = conn.execute(
            select(MessageThread).where(MessageThread.reservation_id == reservation_id)
        ).fetchone()

        assert result is not None
        assert len(result.raw_messages) == 2
        assert result.raw_messages[1]["message"] == "New message"


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [77775], indirect=True)
def test_insert_messages_skips_update_when_messages_unchanged(
    test_account_with_reservation: tuple[int, int],
) -> None:
    """Test that insert_messages skips update when raw_messages is identical."""
    account_id, reservation_id = test_account_with_reservation

    # Insert initial thread
    initial_data = [
        {
            "reservation_id": reservation_id,
            "raw_messages": [
                {"id": 20, "message": "Same message", "sent_at": "2024-01-01T10:00:00Z"},
            ],
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T10:00:00Z",
        }
    ]
    insert_messages(engine, account_id, initial_data)

    # Get initial updated_at timestamp
    with engine.connect() as conn:
        initial_result = conn.execute(
            select(MessageThread.updated_at).where(MessageThread.reservation_id == reservation_id)
        ).fetchone()
        assert initial_result is not None
        initial_updated_at = initial_result[0]

    # Re-insert with identical messages
    insert_messages(engine, account_id, initial_data)

    # Verify updated_at didn't change
    with engine.connect() as conn:
        final_result = conn.execute(
            select(MessageThread.updated_at).where(MessageThread.reservation_id == reservation_id)
        ).fetchone()
        assert final_result is not None
        final_updated_at = final_result[0]

        assert (
            initial_updated_at == final_updated_at
        ), "updated_at should not change when raw_messages is identical"


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [77774], indirect=True)
def test_insert_messages_handles_empty_list(test_account: int) -> None:
    """Test that insert_messages handles empty data list gracefully."""
    account_id = test_account
    data: list[dict[str, Any]] = []

    # Should not raise exception
    insert_messages(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(
            select(MessageThread).where(MessageThread.account_id == account_id)
        ).fetchall()

        assert len(result) == 0


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [77773], indirect=True)
def test_insert_messages_dry_run_mode(test_account_with_reservation: tuple[int, int]) -> None:
    """Test that insert_messages in dry_run mode doesn't write to database."""
    account_id, reservation_id = test_account_with_reservation
    data = [
        {
            "reservation_id": reservation_id,
            "raw_messages": [
                {"id": 30, "message": "Dry run message", "sent_at": "2024-01-01T10:00:00Z"},
            ],
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T10:00:00Z",
        }
    ]

    insert_messages(engine, account_id, data, dry_run=True)

    with engine.connect() as conn:
        result = conn.execute(
            select(MessageThread).where(MessageThread.account_id == account_id)
        ).fetchall()

        # Should be empty because dry_run=True
        assert len(result) == 0


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [77772], indirect=True)
def test_insert_messages_adds_account_id_to_all_rows(
    test_account_with_reservation: tuple[int, int],
) -> None:
    """Test that insert_messages adds account_id to all message thread records."""
    account_id, reservation_id = test_account_with_reservation
    data = [
        {
            "reservation_id": reservation_id,
            "raw_messages": [
                {"id": 40, "message": "Test message", "sent_at": "2024-01-01T10:00:00Z"},
            ],
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T10:00:00Z",
            # Note: account_id NOT in input data
        }
    ]

    insert_messages(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(
            select(MessageThread).where(MessageThread.reservation_id == reservation_id)
        ).fetchone()

        assert result is not None
        assert result.account_id == account_id
