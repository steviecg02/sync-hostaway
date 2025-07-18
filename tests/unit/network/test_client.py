from unittest.mock import Mock, patch

from sync_hostaway.network.client import fetch_page, fetch_paginated

DUMMY_TOKEN = "dummy-token"


@patch("sync_hostaway.network.client.requests.get")
def test_fetch_page_success(mock_get: Mock) -> None:
    """
    Test that fetch_page returns expected JSON structure for a successful 200 response.

    Args:
        mock_get (Mock): Mocked requests.get call.
    """
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "result": [{"id": 1, "name": "Test"}],
        "count": 1,
        "limit": 100,
    }

    result = fetch_page("listings", token=DUMMY_TOKEN, page_number=0)

    assert result["count"] == 1
    assert result["result"][0]["id"] == 1


@patch("sync_hostaway.network.client.fetch_page")
def test_fetch_paginated_multiple_pages(mock_fetch_page: Mock) -> None:
    """
    Test that fetch_paginated aggregates results across multiple mocked pages.

    Args:
        mock_fetch_page (Mock): Mocked fetch_page function.
    """
    mock_fetch_page.side_effect = [
        {"result": [{"id": 1}], "count": 2, "limit": 1},
        {"result": [{"id": 2}]},
    ]

    result = fetch_paginated("listings", token=DUMMY_TOKEN, limit=1)
    ids = [r["id"] for r in result]

    assert ids == [1, 2]
    assert len(result) == 2


@patch("sync_hostaway.network.client.requests.get")
def test_fetch_page_single_result(mock_get: Mock) -> None:
    """
    Test that fetch_page correctly parses a response with a single item.

    Args:
        mock_get (Mock): Mocked requests.get call.
    """
    mock_get.return_value = Mock(status_code=200)
    mock_get.return_value.json.return_value = {
        "result": [{"id": 1}],
        "count": 1,
        "limit": 100,
        "offset": 0,
    }

    result = fetch_page(endpoint="listings", token=DUMMY_TOKEN, page_number=0)
    assert result["result"][0]["id"] == 1
    assert result["count"] == 1


@patch("sync_hostaway.network.client.fetch_page")
def test_fetch_paginated_two_pages(mock_fetch_page: Mock) -> None:
    """
    Test that fetch_paginated collects and returns results from two separate pages.

    Args:
        mock_fetch_page (Mock): Mocked fetch_page function.
    """
    mock_fetch_page.side_effect = [
        {"result": [{"id": 1}], "count": 2, "limit": 1},
        {"result": [{"id": 2}]},
    ]

    results = fetch_paginated(endpoint="listings", token=DUMMY_TOKEN, limit=1)
    assert len(results) == 2
    assert results[0]["id"] == 1
    assert results[1]["id"] == 2


@patch("sync_hostaway.network.client.requests.get")
def test_fetch_page_handles_429_retry(mock_get: Mock) -> None:
    """
    Test that fetch_page retries once after a 429 (rate-limited) response.

    Args:
        mock_get (Mock): Mocked requests.get call.
    """
    retry = Mock(status_code=200)
    retry.json.return_value = {"result": [{"id": 99}], "count": 1, "limit": 100}

    too_many = Mock(status_code=429)
    mock_get.side_effect = [too_many, retry]

    result = fetch_page(endpoint="listings", token=DUMMY_TOKEN, page_number=0)
    assert result["result"][0]["id"] == 99
