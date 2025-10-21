"""Hostaway webhook receiver route."""

import logging
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/hostaway")
async def receive_hostaway_webhook(request: Request) -> JSONResponse:
    """
    Handle incoming Hostaway webhook events.

    Args:
        request (Request): FastAPI request containing the JSON webhook body.

    Returns:
        JSONResponse: Acknowledgment response.
    """
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        logger.exception("Failed to parse webhook payload")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid JSON"},
        )

    event_type: str | None = payload.get("eventType")

    if not event_type:
        logger.warning("Webhook missing eventType: %s", payload)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing eventType"},
        )

    logger.info("Received Hostaway webhook: eventType=%s", event_type)

    # 🧪 TODO: Dispatch to sync handler and/or automation forwarder
    return JSONResponse(content={"status": "accepted"})
