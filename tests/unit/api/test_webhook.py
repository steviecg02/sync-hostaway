"""Unit tests for the Hostaway webhook endpoint."""

import base64
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from sync_hostaway.main import app


def make_basic_auth_header(username: str, password: str) -> str:
    """Create HTTP Basic Auth header."""
    credentials = f"{username}:{password}".encode("utf-8")
    encoded = base64.b64encode(credentials).decode("utf-8")
    return f"Basic {encoded}"


@pytest.mark.asyncio
async def test_webhook_missing_auth() -> None:
    """Test that webhook returns 401 when Authorization header is missing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/hostaway/webhooks", json={"eventType": "reservation.created"})
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
async def test_webhook_invalid_auth() -> None:
    """Test that webhook returns 401 when credentials are invalid."""
    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("wrong", "credentials")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/hostaway/webhooks",
            json={"eventType": "reservation.created"},
            headers={"Authorization": auth_header},
        )
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
async def test_webhook_missing_event_type() -> None:
    """Test that webhook returns 400 when eventType is missing."""
    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/hostaway/webhooks",
            json={},
            headers={"Authorization": auth_header},
        )
    assert response.status_code == 400
    assert response.json() == {"error": "Missing eventType"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
async def test_webhook_missing_account_id() -> None:
    """Test that webhook returns 400 when accountId is missing."""
    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/hostaway/webhooks",
            json={"eventType": "reservation.created"},
            headers={"Authorization": auth_header},
        )
    assert response.status_code == 400
    assert response.json() == {"error": "Missing accountId"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.routes.webhook.validate_account")
async def test_webhook_unknown_account(mock_validate: any, mock_engine: any) -> None:
    """Test that webhook returns 404 when account doesn't exist."""
    mock_validate.return_value = False  # Account not found

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/hostaway/webhooks",
            json={"eventType": "reservation.created", "accountId": 99999},
            headers={"Authorization": auth_header},
        )
    assert response.status_code == 404
    assert "Account 99999 not found" in response.json()["error"]


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
@patch("sync_hostaway.routes.webhook.handle_reservation_created")
async def test_webhook_reservation_created_success(
    mock_handler: any,
    mock_validate: any,
    mock_engine: any,
) -> None:
    """Test that webhook successfully processes reservation.created event."""
    mock_validate.return_value = True  # Account exists

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    payload = {
        "eventType": "reservation.created",
        "accountId": 12345,
        "data": {"id": 789, "status": "new"},
    }

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/hostaway/webhooks",
            json=payload,
            headers={"Authorization": auth_header},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    mock_handler.assert_called_once_with(12345, payload)


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
async def test_webhook_unsupported_event_type(mock_validate: any, mock_engine: any) -> None:
    """Test that webhook accepts but logs warning for unsupported event types."""
    mock_validate.return_value = True  # Account exists

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/hostaway/webhooks",
            json={"eventType": "listing.deleted", "accountId": 12345},
            headers={"Authorization": auth_header},
        )

    # Should return 200 even for unsupported events (don't fail)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
