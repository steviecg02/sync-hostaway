"""Unit tests for sync_account webhook registration flow."""

from unittest.mock import Mock, patch

import pytest

from sync_hostaway.services.sync import sync_account


@pytest.mark.unit
@patch("sync_hostaway.services.sync.register_webhook")
@patch("sync_hostaway.services.sync.update_webhook_id")
@patch("sync_hostaway.services.sync.update_last_sync")
@patch("sync_hostaway.services.sync.insert_messages")
@patch("sync_hostaway.services.sync.normalize_raw_messages")
@patch("sync_hostaway.services.sync.poll_messages")
@patch("sync_hostaway.services.sync.insert_reservations")
@patch("sync_hostaway.services.sync.poll_reservations")
@patch("sync_hostaway.services.sync.insert_listings")
@patch("sync_hostaway.services.sync.poll_listings")
@patch("sync_hostaway.services.sync.engine")
def test_sync_account_registers_webhook_after_sync(
    mock_engine: Mock,
    mock_poll_listings: Mock,
    mock_insert_listings: Mock,
    mock_poll_reservations: Mock,
    mock_insert_reservations: Mock,
    mock_poll_messages: Mock,
    mock_normalize: Mock,
    mock_insert_messages: Mock,
    mock_update_last_sync: Mock,
    mock_update_webhook_id: Mock,
    mock_register_webhook: Mock,
) -> None:
    """Test that sync_account registers webhook after successful sync."""
    # Setup mocks
    mock_poll_listings.return_value = []
    mock_poll_reservations.return_value = []
    mock_poll_messages.return_value = []
    mock_normalize.return_value = []
    mock_register_webhook.return_value = 456  # Webhook ID

    # Run sync
    sync_account(account_id=12345, dry_run=False)

    # Verify webhook registration was called
    mock_register_webhook.assert_called_once_with(12345)
    mock_update_webhook_id.assert_called_once()

    # Check webhook_id was saved
    call_args = mock_update_webhook_id.call_args
    assert call_args.args[1] == 12345  # account_id
    assert call_args.args[2] == 456  # webhook_id


@pytest.mark.unit
@patch("sync_hostaway.services.sync.register_webhook")
@patch("sync_hostaway.services.sync.update_webhook_id")
@patch("sync_hostaway.services.sync.update_last_sync")
@patch("sync_hostaway.services.sync.insert_messages")
@patch("sync_hostaway.services.sync.normalize_raw_messages")
@patch("sync_hostaway.services.sync.poll_messages")
@patch("sync_hostaway.services.sync.insert_reservations")
@patch("sync_hostaway.services.sync.poll_reservations")
@patch("sync_hostaway.services.sync.insert_listings")
@patch("sync_hostaway.services.sync.poll_listings")
@patch("sync_hostaway.services.sync.engine")
def test_sync_account_skips_webhook_on_dry_run(
    mock_engine: Mock,
    mock_poll_listings: Mock,
    mock_insert_listings: Mock,
    mock_poll_reservations: Mock,
    mock_insert_reservations: Mock,
    mock_poll_messages: Mock,
    mock_normalize: Mock,
    mock_insert_messages: Mock,
    mock_update_last_sync: Mock,
    mock_update_webhook_id: Mock,
    mock_register_webhook: Mock,
) -> None:
    """Test that sync_account skips webhook registration on dry_run."""
    # Setup mocks
    mock_poll_listings.return_value = []
    mock_poll_reservations.return_value = []
    mock_poll_messages.return_value = []
    mock_normalize.return_value = []

    # Run sync with dry_run=True
    sync_account(account_id=12345, dry_run=True)

    # Verify webhook registration was NOT called
    mock_register_webhook.assert_not_called()
    mock_update_webhook_id.assert_not_called()
    mock_update_last_sync.assert_not_called()


@pytest.mark.unit
@patch("sync_hostaway.services.sync.register_webhook")
@patch("sync_hostaway.services.sync.update_webhook_id")
@patch("sync_hostaway.services.sync.update_last_sync")
@patch("sync_hostaway.services.sync.insert_messages")
@patch("sync_hostaway.services.sync.normalize_raw_messages")
@patch("sync_hostaway.services.sync.poll_messages")
@patch("sync_hostaway.services.sync.insert_reservations")
@patch("sync_hostaway.services.sync.poll_reservations")
@patch("sync_hostaway.services.sync.insert_listings")
@patch("sync_hostaway.services.sync.poll_listings")
@patch("sync_hostaway.services.sync.engine")
def test_sync_account_continues_on_webhook_failure(
    mock_engine: Mock,
    mock_poll_listings: Mock,
    mock_insert_listings: Mock,
    mock_poll_reservations: Mock,
    mock_insert_reservations: Mock,
    mock_poll_messages: Mock,
    mock_normalize: Mock,
    mock_insert_messages: Mock,
    mock_update_last_sync: Mock,
    mock_update_webhook_id: Mock,
    mock_register_webhook: Mock,
) -> None:
    """Test that sync_account continues even if webhook registration fails."""
    # Setup mocks
    mock_poll_listings.return_value = []
    mock_poll_reservations.return_value = []
    mock_poll_messages.return_value = []
    mock_normalize.return_value = []
    mock_register_webhook.side_effect = Exception("Webhook API error")

    # Run sync - should NOT raise exception
    sync_account(account_id=12345, dry_run=False)

    # Verify sync still completed (last_sync_at was updated)
    mock_update_last_sync.assert_called_once()

    # Webhook ID should NOT be saved since registration failed
    mock_update_webhook_id.assert_not_called()


@pytest.mark.unit
@patch("sync_hostaway.services.sync.register_webhook")
@patch("sync_hostaway.services.sync.update_webhook_id")
@patch("sync_hostaway.services.sync.update_last_sync")
@patch("sync_hostaway.services.sync.insert_messages")
@patch("sync_hostaway.services.sync.normalize_raw_messages")
@patch("sync_hostaway.services.sync.poll_messages")
@patch("sync_hostaway.services.sync.insert_reservations")
@patch("sync_hostaway.services.sync.poll_reservations")
@patch("sync_hostaway.services.sync.insert_listings")
@patch("sync_hostaway.services.sync.poll_listings")
@patch("sync_hostaway.services.sync.engine")
def test_sync_account_handles_webhook_no_id(
    mock_engine: Mock,
    mock_poll_listings: Mock,
    mock_insert_listings: Mock,
    mock_poll_reservations: Mock,
    mock_insert_reservations: Mock,
    mock_poll_messages: Mock,
    mock_normalize: Mock,
    mock_insert_messages: Mock,
    mock_update_last_sync: Mock,
    mock_update_webhook_id: Mock,
    mock_register_webhook: Mock,
) -> None:
    """Test sync_account handles webhook registration returning None."""
    # Setup mocks
    mock_poll_listings.return_value = []
    mock_poll_reservations.return_value = []
    mock_poll_messages.return_value = []
    mock_normalize.return_value = []
    mock_register_webhook.return_value = None  # No webhook ID returned

    # Run sync
    sync_account(account_id=12345, dry_run=False)

    # Verify sync completed
    mock_update_last_sync.assert_called_once()

    # Webhook ID should NOT be saved since None was returned
    mock_update_webhook_id.assert_not_called()
