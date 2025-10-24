"""Unit tests for the Hostaway webhook endpoint."""

import base64
from typing import Any
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
        response = await ac.post(
            "/api/v1/hostaway/webhooks", json={"eventType": "reservation.created"}
        )
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
            "/api/v1/hostaway/webhooks",
            json={"eventType": "reservation.created"},
            headers={"Authorization": auth_header},
        )
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
async def test_webhook_missing_event_type() -> None:
    """Test that webhook returns 400 when event/eventType is missing."""
    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/hostaway/webhooks",
            json={},
            headers={"Authorization": auth_header},
        )
    assert response.status_code == 400
    assert response.json() == {"error": "Missing event or eventType field"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
async def test_webhook_missing_account_id() -> None:
    """Test that webhook returns 400 when accountId is missing."""
    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/hostaway/webhooks",
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
async def test_webhook_unknown_account(mock_validate: Any, mock_engine: Any) -> None:
    """Test that webhook returns 404 when account doesn't exist."""
    mock_validate.return_value = False  # Account not found

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/hostaway/webhooks",
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
    mock_handler: Any,
    mock_validate: Any,
    mock_engine: Any,
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
            "/api/v1/hostaway/webhooks",
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
async def test_webhook_unsupported_event_type(mock_validate: Any, mock_engine: Any) -> None:
    """Test that webhook accepts but logs warning for unsupported event types."""
    mock_validate.return_value = True  # Account exists

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/hostaway/webhooks",
            json={"eventType": "listing.deleted", "accountId": 12345},
            headers={"Authorization": auth_header},
        )

    # Should return 200 even for unsupported events (don't fail)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
@patch("sync_hostaway.routes.webhook.handle_reservation_updated")
async def test_webhook_hostaway_nested_payload_structure(
    mock_handler: Any,
    mock_validate: Any,
    mock_engine: Any,
) -> None:
    """Test that webhook handles Hostaway's actual nested payload structure.

    Hostaway sends webhooks with this structure:
    {
        "object": "reservation",
        "event": "reservation.updated",
        "accountId": 59808,
        "payload": {
            "data": {...}
        }
    }

    This test ensures the webhook endpoint correctly normalizes this structure
    before passing to handlers.
    """
    mock_validate.return_value = True  # Account exists

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    # Real Hostaway payload structure (simplified)
    payload = {
        "object": "reservation",
        "event": "reservation.updated",  # Note: "event" not "eventType"
        "accountId": 59808,
        "payload": {  # Note: nested under "payload"
            "data": {
                "id": 48464658,
                "listingMapId": 218666,
                "guestName": "Test Guest",
                "status": "modified",
            }
        },
    }

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/hostaway/webhooks",
            json=payload,
            headers={"Authorization": auth_header},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}

    # Verify handler was called with normalized payload (payload.data promoted to top level)
    expected_normalized = {
        "data": {
            "id": 48464658,
            "listingMapId": 218666,
            "guestName": "Test Guest",
            "status": "modified",
        }
    }
    mock_handler.assert_called_once_with(59808, expected_normalized)
