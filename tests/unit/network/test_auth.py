"""
Unit tests for network/auth.py token management.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

from sync_hostaway.network.auth import (
    create_access_token,
    get_access_token,
    get_or_refresh_token,
    refresh_access_token,
)


@pytest.mark.unit
@patch("sync_hostaway.network.auth.requests.post")
def test_create_access_token_success(mock_post: Mock) -> None:
    """Test that create_access_token returns token on successful API call."""
    mock_response = Mock()
    mock_response.json.return_value = {"access_token": "test-token-123"}
    mock_post.return_value = mock_response

    token = create_access_token("12345", "test-secret")

    assert token == "test-token-123"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.hostaway.com/v1/accessTokens"
    assert call_args[1]["data"]["client_id"] == "12345"
    assert call_args[1]["data"]["client_secret"] == "test-secret"


@pytest.mark.unit
@patch("sync_hostaway.network.auth.requests.post")
def test_create_access_token_raises_on_http_error(mock_post: Mock) -> None:
    """Test that create_access_token raises HTTPError on API failure."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_response.raise_for_status.side_effect = requests.HTTPError("401 Error")

    mock_post.return_value = mock_response

    with pytest.raises(requests.HTTPError):
        create_access_token("12345", "bad-secret")


@pytest.mark.unit
@patch("sync_hostaway.network.auth.requests.post")
def test_create_access_token_raises_on_missing_token(mock_post: Mock) -> None:
    """Test that create_access_token raises RuntimeError if response lacks access_token."""
    mock_response = Mock()
    mock_response.json.return_value = {"error": "something went wrong"}
    mock_response.text = '{"error": "something went wrong"}'
    mock_post.return_value = mock_response

    with pytest.raises(RuntimeError, match="No access_token in Hostaway response"):
        create_access_token("12345", "test-secret")


@pytest.mark.unit
@patch("sync_hostaway.network.auth.engine")
@patch("sync_hostaway.network.auth.create_access_token")
def test_refresh_access_token_success(mock_create_token: Mock, mock_engine: Mock) -> None:
    """Test that refresh_access_token gets new token and updates DB."""
    account_id = 12345

    # Mock DB connection
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    # Mock get_account_credentials to return valid credentials
    with patch("sync_hostaway.network.auth.get_account_credentials") as mock_get_creds:
        mock_get_creds.return_value = {"client_secret": "test-secret"}

        # Mock create_access_token to return new token
        mock_create_token.return_value = "new-token-456"

        # Mock update_access_token
        with patch("sync_hostaway.network.auth.update_access_token") as mock_update:
            token = refresh_access_token(account_id)

            assert token == "new-token-456"
            mock_get_creds.assert_called_once_with(mock_conn, account_id)
            mock_create_token.assert_called_once_with(str(account_id), "test-secret")
            mock_update.assert_called_once_with(mock_conn, account_id, "new-token-456")


@pytest.mark.unit
@patch("sync_hostaway.network.auth.engine")
def test_refresh_access_token_raises_on_missing_credentials(mock_engine: Mock) -> None:
    """Test that refresh_access_token raises RuntimeError if no credentials found."""
    account_id = 12345

    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    with patch("sync_hostaway.network.auth.get_account_credentials") as mock_get_creds:
        mock_get_creds.return_value = None

        with pytest.raises(RuntimeError, match="No valid Hostaway credentials"):
            refresh_access_token(account_id)


@pytest.mark.unit
@patch("sync_hostaway.network.auth.engine")
def test_refresh_access_token_raises_on_missing_secret(mock_engine: Mock) -> None:
    """Test that refresh_access_token raises RuntimeError if client_secret is missing."""
    account_id = 12345

    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    with patch("sync_hostaway.network.auth.get_account_credentials") as mock_get_creds:
        mock_get_creds.return_value = {"client_secret": None}

        with pytest.raises(RuntimeError, match="No valid Hostaway credentials"):
            refresh_access_token(account_id)


@pytest.mark.unit
@patch("sync_hostaway.network.auth.engine")
def test_get_access_token_returns_existing_token(mock_engine: Mock) -> None:
    """Test that get_access_token returns existing token from DB if valid."""
    account_id = 12345

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("sync_hostaway.network.auth.get_account_credentials") as mock_get_creds:
        mock_get_creds.return_value = {"access_token": "existing-token"}

        token = get_access_token(account_id)

        assert token == "existing-token"
        mock_get_creds.assert_called_once_with(mock_conn, account_id)


@pytest.mark.unit
@patch("sync_hostaway.network.auth.engine")
@patch("sync_hostaway.network.auth.refresh_access_token")
def test_get_access_token_refreshes_if_missing(mock_refresh: Mock, mock_engine: Mock) -> None:
    """Test that get_access_token calls refresh_access_token if token missing."""
    account_id = 12345

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    with patch("sync_hostaway.network.auth.get_account_credentials") as mock_get_creds:
        mock_get_creds.return_value = {"access_token": None}
        mock_refresh.return_value = "refreshed-token"

        token = get_access_token(account_id)

        assert token == "refreshed-token"
        mock_refresh.assert_called_once_with(account_id)


@pytest.mark.unit
@patch("sync_hostaway.network.auth.get_access_token")
def test_get_or_refresh_token_returns_cached_token(mock_get_token: Mock) -> None:
    """Test that get_or_refresh_token returns cached token if valid."""
    account_id = 12345
    mock_get_token.return_value = "valid-token"

    token = get_or_refresh_token(account_id)

    assert token == "valid-token"
    mock_get_token.assert_called_once_with(account_id)


@pytest.mark.unit
@patch("sync_hostaway.network.auth.get_access_token")
@patch("sync_hostaway.network.auth.refresh_access_token")
def test_get_or_refresh_token_refreshes_if_matches_prev_token(
    mock_refresh: Mock, mock_get_token: Mock
) -> None:
    """Test that get_or_refresh_token refreshes if token matches failed prev_token."""
    account_id = 12345
    failed_token = "failed-token"

    mock_get_token.return_value = failed_token
    mock_refresh.return_value = "new-token"

    token = get_or_refresh_token(account_id, prev_token=failed_token)

    assert token == "new-token"
    mock_refresh.assert_called_once_with(account_id)


@pytest.mark.unit
@patch("sync_hostaway.network.auth.get_access_token")
@patch("sync_hostaway.network.auth.refresh_access_token")
def test_get_or_refresh_token_refreshes_if_no_token(
    mock_refresh: Mock, mock_get_token: Mock
) -> None:
    """Test that get_or_refresh_token refreshes if no token found."""
    account_id = 12345

    mock_get_token.return_value = None
    mock_refresh.return_value = "new-token"

    token = get_or_refresh_token(account_id)

    assert token == "new-token"
    mock_refresh.assert_called_once_with(account_id)
