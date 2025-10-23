"""
Integration tests for health and readiness endpoints.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from sync_hostaway.main import app

client = TestClient(app)


@pytest.mark.integration
def test_health_endpoint_returns_ok():
    """Test that /health endpoint returns 200 with status ok."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_readiness_endpoint_returns_ready_when_db_accessible():
    """Test that /ready endpoint returns 200 when database is accessible."""
    response = client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"


@pytest.mark.integration
def test_readiness_endpoint_returns_503_when_db_not_accessible():
    """Test that /ready endpoint returns 503 when database is not accessible."""
    # Mock check_engine_health to simulate database failure
    with patch("sync_hostaway.routes.health.check_engine_health") as mock_health:
        mock_health.return_value = False

        response = client.get("/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not ready"
        assert data["checks"]["database"] == "failed"


@pytest.mark.integration
def test_health_endpoint_always_returns_ok_even_if_db_down():
    """Test that /health endpoint returns 200 even if database is down.

    Health endpoint should only check if the application process is running,
    not if dependencies are available. That's what /ready is for.
    """
    # Health endpoint doesn't check database, so no mocking needed
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
