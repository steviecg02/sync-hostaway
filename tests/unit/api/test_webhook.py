"""Unit tests for the Hostaway webhook endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from sync_hostaway.routes.main import app


@pytest.mark.asyncio
async def test_webhook_missing_event_type() -> None:
    """
    Test that the webhook endpoint returns 400 when 'eventType' is missing.

    This simulates an invalid webhook payload and checks for a proper error response.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/webhook/hostaway", json={})
    assert response.status_code == 400
    assert response.json() == {"error": "Missing eventType"}


@pytest.mark.asyncio
async def test_webhook_valid_event_type() -> None:
    """
    Test that the webhook endpoint accepts a valid payload with 'eventType'.

    This simulates a well-formed webhook and checks for a 200 OK response.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/webhook/hostaway", json={"eventType": "reservationModified"})
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
