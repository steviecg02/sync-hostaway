from unittest.mock import MagicMock, patch

from sync_hostaway.pollers.listings import poll_listings


@patch("sync_hostaway.pollers.listings.fetch_paginated")
def test_poll_listings_returns_data(mock_fetch: MagicMock) -> None:
    """
    Ensure poll_listings returns fetched listing data.
    """
    mock_fetch.return_value = [{"id": 1, "name": "Apt A"}, {"id": 2, "name": "Apt B"}]

    result = poll_listings(account_id=12345)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["id"] == 1


@patch("sync_hostaway.pollers.listings.fetch_paginated")
def test_poll_listings_returns_empty_if_none(mock_fetch: MagicMock) -> None:
    """
    Ensure poll_listings handles empty response gracefully.
    """
    mock_fetch.return_value = []

    result = poll_listings(account_id=12345)
    assert result == []
