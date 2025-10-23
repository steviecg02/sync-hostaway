"""
Unit tests for metrics endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sync_hostaway.main import app
from sync_hostaway.metrics import (
    api_latency,
    api_requests,
    poll_duration,
    poll_total,
    records_synced,
)


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    return TestClient(app)


@pytest.mark.unit
def test_metrics_endpoint_returns_prometheus_format(client: TestClient) -> None:
    """Test that /metrics endpoint returns Prometheus text format."""
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.unit
def test_metrics_endpoint_contains_custom_metrics(client: TestClient) -> None:
    """Test that /metrics endpoint includes our custom Hostaway metrics."""
    # Record some test metrics
    poll_total.labels(account_id="999", entity_type="listings", status="success").inc()
    records_synced.labels(account_id="999", entity_type="listings").inc(5)
    poll_duration.labels(account_id="999", entity_type="listings").observe(1.23)
    api_requests.labels(endpoint="listings", status_code="200").inc()
    api_latency.labels(endpoint="listings").observe(0.45)

    response = client.get("/metrics")
    content = response.text

    # Verify our custom metrics appear in output
    assert "hostaway_polls_total" in content
    assert "hostaway_records_synced_total" in content
    assert "hostaway_poll_duration_seconds" in content
    assert "hostaway_api_requests_total" in content
    assert "hostaway_api_latency_seconds" in content


@pytest.mark.unit
def test_metrics_endpoint_includes_help_and_type_metadata(client: TestClient) -> None:
    """Test that metrics include Prometheus HELP and TYPE metadata."""
    response = client.get("/metrics")
    content = response.text

    # Prometheus format includes HELP and TYPE lines
    assert "# HELP" in content
    assert "# TYPE" in content
    assert "counter" in content or "histogram" in content or "gauge" in content
