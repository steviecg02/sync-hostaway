"""
Prometheus metrics endpoint for monitoring and observability.

This module provides a FastAPI route that exposes Prometheus metrics in the
standard text-based format for scraping by Prometheus servers.

Example:
    GET /metrics

    Response:
        # HELP hostaway_polls_total Total number of polling operations
        # TYPE hostaway_polls_total counter
        hostaway_polls_total{account_id="12345",entity_type="listings",status="success"} 42.0
        ...
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter()


@router.get("/metrics", response_class=Response)
async def metrics() -> Any:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text-based exposition format. This endpoint
    should be scraped by Prometheus at regular intervals (e.g., every 15-30 seconds).

    Returns:
        Response: Metrics in Prometheus format with Content-Type: text/plain

    Example Response:
        # HELP hostaway_polls_total Total polling operations
        # TYPE hostaway_polls_total counter
        hostaway_polls_total{account_id="12345",entity_type="listings"} 42.0

        # HELP hostaway_poll_duration_seconds Poll duration
        # TYPE hostaway_poll_duration_seconds histogram
        hostaway_poll_duration_seconds_bucket{le="0.5"} 10.0
        ...
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
