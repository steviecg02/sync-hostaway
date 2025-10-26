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


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
@patch("sync_hostaway.routes.webhook.insert_reservations")
async def test_webhook_reservation_created_real_payload(
    mock_insert: Any,
    mock_validate: Any,
    mock_engine: Any,
) -> None:
    """Test reservation.created with real Hostaway payload structure."""
    mock_validate.return_value = True

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    # Real Hostaway reservation.created payload structure
    payload = {
        "object": "reservation",
        "event": "reservation.created",
        "accountId": 59808,
        "data": {
            "id": 49264388,
            "listingMapId": 218666,
            "listingName": "211 N Wilbur Ave",
            "channelId": 2018,
            "channelName": "airbnbOfficial",
            "guestName": "Logan",
            "guestFirstName": "Logan",
            "guestLastName": None,
            "status": "pending",
            "arrivalDate": "2025-11-21",
            "departureDate": "2025-11-23",
            "nights": 2,
            "totalPrice": 696.67,
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
    mock_insert.assert_called_once()


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
@patch("sync_hostaway.routes.webhook.insert_reservations")
async def test_webhook_reservation_updated_real_payload(
    mock_insert: Any,
    mock_validate: Any,
    mock_engine: Any,
) -> None:
    """Test reservation.updated with real Hostaway payload structure."""
    mock_validate.return_value = True

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    # Real Hostaway reservation.updated payload structure
    payload = {
        "object": "reservation",
        "event": "reservation.updated",
        "accountId": 59808,
        "data": {
            "id": 49264388,
            "listingMapId": 218666,
            "listingName": "211 N Wilbur Ave",
            "guestName": "Logan Dix",
            "guestFirstName": "Logan",
            "guestLastName": "Dix",
            "status": "new",
            "phone": "+16478641271",
            "arrivalDate": "2025-11-21",
            "departureDate": "2025-11-23",
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
    mock_insert.assert_called_once()


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
async def test_webhook_message_received_real_payload(
    mock_validate: Any,
    mock_engine: Any,
) -> None:
    """Test message.received with real Hostaway payload structure."""
    mock_validate.return_value = True

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    # Real Hostaway message.received payload structure
    payload = {
        "object": "conversationMessage",
        "event": "message.received",
        "accountId": 59808,
        "data": {
            "id": 340127415,
            "accountId": 59808,
            "listingMapId": 218666,
            "reservationId": 49264388,
            "conversationId": 35460020,
            "channelId": 2018,
            "body": "Hi, can't wait to enjoy our stay at your home. My family is all meeting up.",
            "isIncoming": 1,
            "isSeen": 0,
            "date": "2025-10-25 15:30:19",
            "status": "sent",
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
    # Message handler is a stub, so just verify 200 response


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
async def test_webhook_reservation_missing_data_field(
    mock_validate: Any,
    mock_engine: Any,
) -> None:
    """Test that webhook handles reservation with missing data field gracefully."""
    mock_validate.return_value = True

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    # Malformed payload - missing data field
    payload = {
        "object": "reservation",
        "event": "reservation.created",
        "accountId": 59808,
        # Missing "data" field
    }

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/hostaway/webhooks",
            json=payload,
            headers={"Authorization": auth_header},
        )

    # Should still return 200 (webhook accepted) but log warning with full payload
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
async def test_webhook_message_missing_data_field(
    mock_validate: Any,
    mock_engine: Any,
) -> None:
    """Test that webhook handles message with missing data field gracefully."""
    mock_validate.return_value = True

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    # Malformed payload - missing data field
    payload = {
        "object": "conversationMessage",
        "event": "message.received",
        "accountId": 59808,
        # Missing "data" field
    }

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/hostaway/webhooks",
            json=payload,
            headers={"Authorization": auth_header},
        )

    # Should still return 200 (webhook accepted) but log warning with full payload
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


@pytest.mark.asyncio
@patch("sync_hostaway.routes.webhook.WEBHOOK_USERNAME", "testuser")
@patch("sync_hostaway.routes.webhook.WEBHOOK_PASSWORD", "testpass")
@patch("sync_hostaway.routes.webhook.engine")
@patch("sync_hostaway.services.account_cache.validate_account")
@patch("sync_hostaway.routes.webhook.insert_reservations")
async def test_webhook_reservation_handler_exception(
    mock_insert: Any,
    mock_validate: Any,
    mock_engine: Any,
) -> None:
    """Test that webhook handles handler exceptions and returns 500."""
    mock_validate.return_value = True
    mock_insert.side_effect = Exception("Database connection failed")

    transport = ASGITransport(app=app)
    auth_header = make_basic_auth_header("testuser", "testpass")

    payload = {
        "object": "reservation",
        "event": "reservation.created",
        "accountId": 59808,
        "data": {
            "id": 49264388,
            "listingMapId": 218666,
            "guestName": "Test Guest",
            "status": "pending",
        },
    }

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/hostaway/webhooks",
            json=payload,
            headers={"Authorization": auth_header},
        )

    # Should return 500 when handler throws exception
    assert response.status_code == 500
    assert "error" in response.json()
