import json
from unittest.mock import MagicMock, patch

from sync_hostaway.pollers.reservations import poll_reservations

DUMMY_RES = [{"id": 1, "guest": "John Doe"}]


@patch("sync_hostaway.pollers.reservations.fetch_paginated")
def test_poll_reservations_calls_dependencies(mock_fetch: MagicMock) -> None:
    """
    Ensure poll_reservations fetches data using token and paginated client.
    """
    mock_fetch.return_value = DUMMY_RES

    result = poll_reservations(account_id=12345)

    mock_fetch.assert_called_once_with("reservations", account_id=12345)
    assert result == DUMMY_RES


@patch("sync_hostaway.pollers.reservations.fetch_paginated")
@patch("sync_hostaway.pollers.reservations.logger")
@patch("sync_hostaway.pollers.reservations.DEBUG", True)
def test_poll_reservations_logs_sample(
    mock_logger: MagicMock, mock_fetch: MagicMock
) -> None:
    """
    If DEBUG is True, the sample reservation should be logged.
    """
    mock_fetch.return_value = DUMMY_RES

    poll_reservations(account_id=12345)

    mock_logger.debug.assert_any_call("Sample reservation:\n%s", json.dumps(DUMMY_RES[0], indent=2))
