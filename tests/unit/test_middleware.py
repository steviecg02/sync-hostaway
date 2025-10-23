"""
Unit tests for middleware components.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sync_hostaway.middleware import RequestIDMiddleware


@pytest.fixture
def app_with_middleware() -> FastAPI:
    """Create FastAPI app with RequestIDMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/test")
    async def test_endpoint(request: Request) -> dict[str, str]:
        """Test endpoint that returns the request ID."""
        return {"request_id": request.state.request_id}

    return app


@pytest.fixture
def client(app_with_middleware: FastAPI) -> TestClient:
    """FastAPI test client with middleware."""
    return TestClient(app_with_middleware)


@pytest.mark.unit
def test_request_id_middleware_adds_header(client: TestClient) -> None:
    """Test that RequestIDMiddleware adds X-Request-ID header to response."""
    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) == 36  # UUID length


@pytest.mark.unit
def test_request_id_middleware_stores_in_request_state(client: TestClient) -> None:
    """Test that RequestIDMiddleware stores request ID in request.state."""
    response = client.get("/test")

    assert response.status_code == 200
    data = response.json()
    assert "request_id" in data
    assert len(data["request_id"]) == 36  # UUID length


@pytest.mark.unit
def test_request_id_middleware_matches_header_and_state(client: TestClient) -> None:
    """Test that request ID in header matches request ID in state."""
    response = client.get("/test")

    assert response.status_code == 200
    header_request_id = response.headers["X-Request-ID"]
    state_request_id = response.json()["request_id"]

    assert header_request_id == state_request_id


@pytest.mark.unit
def test_request_id_middleware_unique_per_request(client: TestClient) -> None:
    """Test that each request gets a unique request ID."""
    response1 = client.get("/test")
    response2 = client.get("/test")

    request_id1 = response1.headers["X-Request-ID"]
    request_id2 = response2.headers["X-Request-ID"]

    assert request_id1 != request_id2
