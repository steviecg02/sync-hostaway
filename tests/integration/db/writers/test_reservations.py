"""
Integration tests for reservations database writer.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from sync_hostaway.db.engine import engine
from sync_hostaway.db.writers.reservations import insert_reservations
from sync_hostaway.models.reservations import Reservation


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [88888], indirect=True)
def test_insert_reservations_creates_new_records(test_account):
    """Test that insert_reservations creates new reservation records in database."""
    account_id = test_account
    data = [
        {
            "id": 6001,
            "listingMapId": 1001,
            "guestName": "John Doe",
            "status": "confirmed",
        },
        {
            "id": 6002,
            "listingMapId": 1002,
            "guestName": "Jane Smith",
            "status": "pending",
        },
    ]

    insert_reservations(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(
            select(Reservation).where(Reservation.account_id == account_id).order_by(Reservation.id)
        ).fetchall()

        assert len(result) == 2
        assert result[0].id == 6001
        assert result[0].account_id == account_id
        assert result[0].listing_id == 1001
        assert result[0].raw_payload["guestName"] == "John Doe"
        assert result[1].id == 6002
        assert result[1].listing_id == 1002


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [88887], indirect=True)
def test_insert_reservations_updates_existing_when_payload_changes(test_account):
    """Test that insert_reservations updates existing records when payload changes."""
    account_id = test_account
    reservation_id = 7001

    # Insert initial reservation
    initial_data = [
        {
            "id": reservation_id,
            "listingMapId": 2001,
            "guestName": "Original Guest",
            "status": "pending",
        }
    ]
    insert_reservations(engine, account_id, initial_data)

    # Update with changed payload
    updated_data = [
        {
            "id": reservation_id,
            "listingMapId": 2001,
            "guestName": "Updated Guest",
            "status": "confirmed",
        }
    ]
    insert_reservations(engine, account_id, updated_data)

    with engine.connect() as conn:
        result = conn.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        ).fetchone()

        assert result is not None
        assert result.raw_payload["guestName"] == "Updated Guest"
        assert result.raw_payload["status"] == "confirmed"


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [88886], indirect=True)
def test_insert_reservations_skips_update_when_payload_unchanged(test_account):
    """Test that insert_reservations skips update when payload is identical."""
    account_id = test_account
    reservation_id = 8001

    # Insert initial reservation
    initial_data = [
        {
            "id": reservation_id,
            "listingMapId": 3001,
            "guestName": "Same Guest",
            "status": "confirmed",
        }
    ]
    insert_reservations(engine, account_id, initial_data)

    # Get initial updated_at timestamp
    with engine.connect() as conn:
        initial_result = conn.execute(
            select(Reservation.updated_at).where(Reservation.id == reservation_id)
        ).fetchone()
        initial_updated_at = initial_result[0]

    # Re-insert with identical payload
    insert_reservations(engine, account_id, initial_data)

    # Verify updated_at didn't change
    with engine.connect() as conn:
        final_result = conn.execute(
            select(Reservation.updated_at).where(Reservation.id == reservation_id)
        ).fetchone()
        final_updated_at = final_result[0]

        assert (
            initial_updated_at == final_updated_at
        ), "updated_at should not change when payload is identical"


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [88885], indirect=True)
def test_insert_reservations_skips_invalid_records(test_account):
    """Test that insert_reservations skips records with missing required fields."""
    account_id = test_account
    data = [
        {"id": 9001, "listingMapId": 4001, "guestName": "Valid Guest 1"},
        {"id": 9002, "guestName": "Invalid - No listing_id"},  # Missing listingMapId
        {"listingMapId": 4002, "guestName": "Invalid - No id"},  # Missing id
        {"id": 9003, "listingMapId": 4003, "guestName": "Valid Guest 2"},
    ]

    # Should not raise exception, just skip invalid records
    insert_reservations(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(
            select(Reservation).where(Reservation.account_id == account_id).order_by(Reservation.id)
        ).fetchall()

        # Should only insert the 2 valid reservations
        assert len(result) == 2
        assert result[0].id == 9001
        assert result[1].id == 9003


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [88884], indirect=True)
def test_insert_reservations_handles_empty_list(test_account):
    """Test that insert_reservations handles empty data list gracefully."""
    account_id = test_account
    data = []

    # Should not raise exception
    insert_reservations(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(
            select(Reservation).where(Reservation.account_id == account_id)
        ).fetchall()

        assert len(result) == 0


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [88883], indirect=True)
def test_insert_reservations_dry_run_mode(test_account):
    """Test that insert_reservations in dry_run mode doesn't write to database."""
    account_id = test_account
    data = [{"id": 10001, "listingMapId": 5001, "guestName": "Dry Run Guest", "status": "pending"}]

    insert_reservations(engine, account_id, data, dry_run=True)

    with engine.connect() as conn:
        result = conn.execute(
            select(Reservation).where(Reservation.account_id == account_id)
        ).fetchall()

        # Should be empty because dry_run=True
        assert len(result) == 0
