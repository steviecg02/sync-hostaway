import pytest
import requests

from sync_hostaway.network.client import fetch_page


def test_fetch_page_with_invalid_token_raises_http_error() -> None:
    """
    Ensure that fetch_page raises HTTPError when given an invalid token.
    """
    with pytest.raises(requests.HTTPError) as exc_info:
        fetch_page("listings", token="invalid-token", page_number=0)

    assert exc_info.value.response.status_code == 403
