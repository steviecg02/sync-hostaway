"""
FastAPI middleware for request tracing and correlation.

This module provides middleware components for adding observability to HTTP requests,
including unique request IDs for distributed tracing and log correlation.
"""

from __future__ import annotations

import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add unique request IDs to each HTTP request.

    This middleware generates a UUID for each incoming request and:
    1. Stores it in request.state.request_id for access in route handlers
    2. Adds it to the response as X-Request-ID header for client correlation
    3. Makes it available for structured logging throughout the request lifecycle

    The request ID can be used to trace a single request through logs, across
    multiple services, and correlate frontend actions with backend operations.

    Example:
        >>> # In main.py
        >>> from sync_hostaway.middleware import RequestIDMiddleware
        >>> app.add_middleware(RequestIDMiddleware)
        >>>
        >>> # In a route handler
        >>> @router.post("/accounts")
        >>> def create_account(request: Request):
        ...     request_id = request.state.request_id
        ...     logger.info("Creating account", request_id=request_id)
        ...     return {"id": 123}
        >>>
        >>> # Response headers will include:
        >>> # X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process each request by adding a unique request ID.

        Args:
            request: Incoming FastAPI request
            call_next: Next middleware or route handler in chain

        Returns:
            Response with X-Request-ID header added
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Store in request state for access in route handlers and logging
        request.state.request_id = request_id

        # Process request through rest of middleware stack and route handler
        response = await call_next(request)

        # Add request ID to response headers for client-side correlation
        response.headers["X-Request-ID"] = request_id

        return response
