"""Unit tests for webhook registration service."""

from unittest.mock import Mock, patch

import pytest
import requests

from sync_hostaway.services.webhook_registration import delete_webhook, register_webhook


@pytest.mark.unit
@patch("sync_hostaway.services.webhook_registration.get_or_refresh_token")
@patch("sync_hostaway.services.webhook_registration.requests.post")
def test_register_webhook_success(mock_post: Mock, mock_get_token: Mock) -> None:
    """Test successful webhook registration returns webhook_id."""
    mock_get_token.return_value = "test-token-123"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"id": 456}}
    mock_post.return_value = mock_response

    webhook_id = register_webhook(account_id=12345)

    assert webhook_id == 456
    mock_post.assert_called_once()

    # Check the payload sent to Hostaway
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["isEnabled"] == 1
    assert "/hostaway/webhooks" in call_kwargs["json"]["url"]
    assert call_kwargs["json"]["login"] is None
    assert call_kwargs["json"]["password"] is None


@pytest.mark.unit
@patch("sync_hostaway.services.webhook_registration.get_or_refresh_token")
@patch("sync_hostaway.services.webhook_registration.requests.post")
def test_register_webhook_no_id_in_response(mock_post: Mock, mock_get_token: Mock) -> None:
    """Test webhook registration handles missing ID in response."""
    mock_get_token.return_value = "test-token-123"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {}}  # No 'id' field
    mock_post.return_value = mock_response

    webhook_id = register_webhook(account_id=12345)

    assert webhook_id is None


@pytest.mark.unit
@patch("sync_hostaway.services.webhook_registration.get_or_refresh_token")
@patch("sync_hostaway.services.webhook_registration.requests.post")
def test_register_webhook_http_error(mock_post: Mock, mock_get_token: Mock) -> None:
    """Test webhook registration raises HTTPError on API failure."""
    mock_get_token.return_value = "test-token-123"

    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
    mock_post.return_value = mock_response

    with pytest.raises(requests.HTTPError):
        register_webhook(account_id=12345)


@pytest.mark.unit
@patch("sync_hostaway.services.webhook_registration.get_or_refresh_token")
@patch("sync_hostaway.services.webhook_registration.requests.delete")
def test_delete_webhook_success(mock_delete: Mock, mock_get_token: Mock) -> None:
    """Test successful webhook deletion returns True."""
    mock_get_token.return_value = "test-token-123"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_delete.return_value = mock_response

    result = delete_webhook(account_id=12345, webhook_id=456)

    assert result is True
    mock_delete.assert_called_once()
    assert "456" in mock_delete.call_args.args[0]


@pytest.mark.unit
@patch("sync_hostaway.services.webhook_registration.get_or_refresh_token")
@patch("sync_hostaway.services.webhook_registration.requests.delete")
def test_delete_webhook_http_error(mock_delete: Mock, mock_get_token: Mock) -> None:
    """Test webhook deletion returns False on API error."""
    mock_get_token.return_value = "test-token-123"

    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)
    mock_delete.return_value = mock_response

    result = delete_webhook(account_id=12345, webhook_id=456)

    assert result is False


@pytest.mark.unit
@patch("sync_hostaway.services.webhook_registration.WEBHOOK_BASE_URL", "https://test.example.com")
@patch("sync_hostaway.services.webhook_registration.get_or_refresh_token")
@patch("sync_hostaway.services.webhook_registration.requests.post")
def test_register_webhook_uses_base_url(mock_post: Mock, mock_get_token: Mock) -> None:
    """Test webhook registration uses configured base URL."""
    mock_get_token.return_value = "test-token-123"

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"id": 789}}
    mock_post.return_value = mock_response

    register_webhook(account_id=12345)

    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["url"] == "https://test.example.com/hostaway/webhooks"
