from unittest.mock import MagicMock, patch

from sync_hostaway.pollers.listings import poll_listings


@patch("sync_hostaway.pollers.listings.fetch_paginated")
@patch("sync_hostaway.pollers.listings.get_access_token")
def test_poll_listings_returns_data(mock_get_token: MagicMock, mock_fetch: MagicMock) -> None:
    """
    Ensure poll_listings returns fetched listing data.
    """
    mock_get_token.return_value = "fake-token"
    mock_fetch.return_value = [{"id": 1, "name": "Apt A"}, {"id": 2, "name": "Apt B"}]

    result = poll_listings()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["id"] == 1


@patch("sync_hostaway.pollers.listings.fetch_paginated")
@patch("sync_hostaway.pollers.listings.get_access_token")
def test_poll_listings_returns_empty_if_none(
    mock_get_token: MagicMock, mock_fetch: MagicMock
) -> None:
    """
    Ensure poll_listings handles empty response gracefully.
    """
    mock_get_token.return_value = "fake-token"
    mock_fetch.return_value = []

    result = poll_listings()
    assert result == []
