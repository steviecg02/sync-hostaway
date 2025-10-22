from typing import Any
from unittest.mock import Mock, patch

import requests

from sync_hostaway.network.client import fetch_page, fetch_paginated


@patch("sync_hostaway.network.client.get_or_refresh_token")
@patch("sync_hostaway.network.client.fetch_page")
def test_fetch_paginated_multiple_pages(mock_fetch_page: Mock, mock_get_token: Mock) -> None:
    """
    Ensure fetch_paginated aggregates results across multiple pages.

    Args:
        mock_fetch_page (Mock): Mocked fetch_page function.
        mock_get_token (Mock): Mocked get_or_refresh_token function.
    """
    mock_get_token.return_value = "dummy-token"
    mock_fetch_page.side_effect = [
        ({"result": [{"id": 1}], "count": 3, "limit": 1}, 200),
        ({"result": [{"id": 2}], "count": 3, "limit": 1}, 200),
        ({"result": [{"id": 3}], "count": 3, "limit": 1}, 200),
    ]

    result = fetch_paginated("listings", account_id=12345, limit=1)

    assert isinstance(result, list)
    assert len(result) == 3
    assert result == [{"id": 1}, {"id": 2}, {"id": 3}]


@patch("sync_hostaway.network.client.get_or_refresh_token")
@patch("sync_hostaway.network.client.fetch_page")
def test_fetch_paginated_single_page(mock_fetch_page: Mock, mock_get_token: Mock) -> None:
    """
    Verify fetch_paginated returns correct results when all data fits on a single page.

    Args:
        mock_fetch_page (Mock): Mocked fetch_page function.
        mock_get_token (Mock): Mocked get_or_refresh_token function.
    """
    mock_get_token.return_value = "dummy-token"
    mock_fetch_page.return_value = (
        {
            "result": [{"id": 1}, {"id": 2}],
            "count": 2,
            "limit": 100,
        },
        200,
    )

    result = fetch_paginated("listings", account_id=12345)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["id"] == 1


@patch("sync_hostaway.network.client.requests.get")
def test_fetch_page_handles_429_retry(mock_get: Mock) -> None:
    """
    Ensure fetch_page retries on 429 rate-limit response and eventually succeeds.

    Args:
        mock_get (Mock): Mocked requests.get function.
    """
    call_count = {"count": 0}

    def side_effect(*args: Any, **kwargs: Any) -> Mock:
        if call_count["count"] == 0:
            call_count["count"] += 1
            mock_resp = Mock(status_code=429)
            mock_resp.raise_for_status.side_effect = requests.HTTPError("429")
            return mock_resp
        else:
            return Mock(status_code=200, json=lambda: {"result": [], "count": 0, "limit": 100})

    mock_get.side_effect = side_effect

    data, status_code = fetch_page("listings", token="dummy-token", page_number=0)

    assert status_code == 200
    assert isinstance(data, dict)
    assert data["result"] == []
