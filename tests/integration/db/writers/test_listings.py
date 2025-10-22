"""
Integration tests for listings database writer.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from sync_hostaway.db.engine import engine
from sync_hostaway.db.writers.listings import insert_listings
from sync_hostaway.models.listings import Listing


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [99999], indirect=True)
def test_insert_listings_creates_new_records(test_account):
    """Test that insert_listings creates new listing records in database."""
    account_id = test_account
    data = [
        {"id": 1001, "name": "Test Listing 1", "address": "123 Main St"},
        {"id": 1002, "name": "Test Listing 2", "address": "456 Oak Ave"},
    ]

    insert_listings(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(
            select(Listing).where(Listing.account_id == account_id).order_by(Listing.id)
        ).fetchall()

        assert len(result) == 2
        assert result[0].id == 1001
        assert result[0].account_id == account_id
        assert result[0].raw_payload["name"] == "Test Listing 1"
        assert result[1].id == 1002
        assert result[1].raw_payload["name"] == "Test Listing 2"


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [99998], indirect=True)
def test_insert_listings_updates_existing_records_when_payload_changes(test_account):
    """Test that insert_listings updates existing listings when raw_payload changes."""
    account_id = test_account
    listing_id = 2001

    # Insert initial listing
    initial_data = [{"id": listing_id, "name": "Original Name", "status": "active"}]
    insert_listings(engine, account_id, initial_data)

    # Update with changed payload
    updated_data = [{"id": listing_id, "name": "Updated Name", "status": "inactive"}]
    insert_listings(engine, account_id, updated_data)

    with engine.connect() as conn:
        result = conn.execute(select(Listing).where(Listing.id == listing_id)).fetchone()

        assert result is not None
        assert result.raw_payload["name"] == "Updated Name"
        assert result.raw_payload["status"] == "inactive"


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [99997], indirect=True)
def test_insert_listings_skips_update_when_payload_unchanged(test_account):
    """Test that insert_listings skips update when raw_payload is identical (IS DISTINCT FROM)."""
    account_id = test_account
    listing_id = 3001

    # Insert initial listing
    initial_data = [{"id": listing_id, "name": "Same Name", "status": "active"}]
    insert_listings(engine, account_id, initial_data)

    # Get initial updated_at timestamp
    with engine.connect() as conn:
        initial_result = conn.execute(
            select(Listing.updated_at).where(Listing.id == listing_id)
        ).fetchone()
        initial_updated_at = initial_result[0]

    # Re-insert with identical payload
    insert_listings(engine, account_id, initial_data)

    # Verify updated_at didn't change (meaning no UPDATE occurred)
    with engine.connect() as conn:
        final_result = conn.execute(
            select(Listing.updated_at).where(Listing.id == listing_id)
        ).fetchone()
        final_updated_at = final_result[0]

        assert (
            initial_updated_at == final_updated_at
        ), "updated_at should not change when payload is identical"


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [99996], indirect=True)
def test_insert_listings_skips_invalid_records(test_account):
    """Test that insert_listings skips listings with missing id."""
    account_id = test_account
    data = [
        {"id": 4001, "name": "Valid Listing"},
        {"name": "Invalid - No ID"},  # Missing id
        {"id": 4002, "name": "Another Valid Listing"},
    ]

    insert_listings(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(select(Listing).where(Listing.account_id == account_id)).fetchall()

        # Should only insert the 2 valid listings
        assert len(result) == 2
        assert result[0].id == 4001
        assert result[1].id == 4002


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [99995], indirect=True)
def test_insert_listings_handles_empty_list(test_account):
    """Test that insert_listings handles empty data list gracefully."""
    account_id = test_account
    data = []

    # Should not raise exception
    insert_listings(engine, account_id, data)

    with engine.connect() as conn:
        result = conn.execute(select(Listing).where(Listing.account_id == account_id)).fetchall()

        assert len(result) == 0


@pytest.mark.integration
@pytest.mark.parametrize("test_account", [99994], indirect=True)
def test_insert_listings_dry_run_mode(test_account):
    """Test that insert_listings in dry_run mode doesn't write to database."""
    account_id = test_account
    data = [{"id": 5001, "name": "Dry Run Listing"}]

    insert_listings(engine, account_id, data, dry_run=True)

    with engine.connect() as conn:
        result = conn.execute(select(Listing).where(Listing.account_id == account_id)).fetchall()

        # Should be empty because dry_run=True
        assert len(result) == 0
