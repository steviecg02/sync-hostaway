"""
Health and readiness check endpoints for Kubernetes probes.

Health checks are used by container orchestration platforms to determine
if the application should be restarted or if it can receive traffic.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from sync_hostaway.db.engine import engine

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def health_check() -> JSONResponse:
    """
    Liveness probe endpoint.

    Returns 200 if the application is running. Used by Kubernetes to
    determine if the container should be restarted.

    Returns:
        JSONResponse with status "ok"

    Example:
        >>> GET /health
        {"status": "ok"}
    """
    return JSONResponse(content={"status": "ok"})


@router.get("/ready")
def readiness_check() -> JSONResponse:
    """
    Readiness probe endpoint.

    Returns 200 if the application can serve traffic (database is accessible).
    Used by Kubernetes to determine if the container should receive traffic.

    Returns:
        JSONResponse with status "ready" and checks object

    Returns 503 if database is not accessible.

    Example:
        >>> GET /ready
        {"status": "ready", "checks": {"database": "ok"}}
    """
    checks = {}

    # Check database connectivity
    try:
        with engine.connect() as conn:
            # Simple query to verify database is accessible
            conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
    except Exception as e:
        logger.error("Readiness check failed: database not accessible: %s", str(e))
        checks["database"] = "failed"
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "checks": checks},
        )

    return JSONResponse(content={"status": "ready", "checks": checks})
