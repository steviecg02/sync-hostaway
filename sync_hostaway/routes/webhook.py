"""Hostaway webhook receiver route."""

import base64
import logging
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from sync_hostaway.config import WEBHOOK_PASSWORD, WEBHOOK_USERNAME
from sync_hostaway.db.engine import engine
from sync_hostaway.db.writers.reservations import insert_reservations
from sync_hostaway.services.account_cache import validate_account

router = APIRouter()
logger = logging.getLogger(__name__)


def validate_basic_auth(auth_header: str | None) -> bool:
    """
    Validate HTTP Basic Auth credentials against global webhook credentials.

    Args:
        auth_header: Authorization header value (e.g., "Basic dXNlcjpwYXNz")

    Returns:
        bool: True if credentials match, False otherwise
    """
    if not auth_header or not auth_header.startswith("Basic "):
        return False

    try:
        # Decode base64 credentials
        encoded_credentials = auth_header.replace("Basic ", "")
        decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
        username, password = decoded_credentials.split(":", 1)

        # Compare against global webhook credentials
        return username == WEBHOOK_USERNAME and password == WEBHOOK_PASSWORD
    except Exception:
        logger.exception("Failed to decode Basic Auth header")
        return False


def handle_reservation_created(account_id: int, payload: dict[str, Any]) -> None:
    """
    Handle reservation.created webhook event.

    Args:
        account_id: Hostaway account ID
        payload: Webhook payload containing reservation data
    """
    reservation_data = payload.get("data", {})
    if not reservation_data:
        logger.warning("reservation.created webhook missing data field")
        return

    insert_reservations(engine, account_id, [reservation_data])
    logger.info("Inserted reservation from webhook: account=%s", account_id)


def handle_reservation_updated(account_id: int, payload: dict[str, Any]) -> None:
    """
    Handle reservation.updated webhook event.

    Args:
        account_id: Hostaway account ID
        payload: Webhook payload containing reservation data
    """
    reservation_data = payload.get("data", {})
    if not reservation_data:
        logger.warning("reservation.updated webhook missing data field")
        return

    insert_reservations(engine, account_id, [reservation_data])
    logger.info("Updated reservation from webhook: account=%s", account_id)


def handle_message_received(account_id: int, payload: dict[str, Any]) -> None:
    """
    Handle message.received webhook event.

    TODO: Implement full conversation fetching logic.
    For now, this is a stub - we need to see actual webhook payloads
    to determine the correct API endpoint and data structure.

    Args:
        account_id: Hostaway account ID
        payload: Webhook payload containing message data
    """
    logger.info("message.received webhook received (stubbed): account=%s", account_id)
    # TODO: Extract conversationId, fetch full conversation, normalize, insert


@router.post("/webhooks")
async def receive_hostaway_webhook(request: Request) -> JSONResponse:
    """
    Handle incoming Hostaway webhook events.

    Supports only 3 event types:
    - reservation.created
    - reservation.updated
    - message.received

    Authentication: HTTP Basic Auth with global WEBHOOK_USERNAME/WEBHOOK_PASSWORD

    Args:
        request: FastAPI request containing webhook payload

    Returns:
        JSONResponse: Acknowledgment response
    """
    # Validate authentication
    auth_header = request.headers.get("Authorization")
    if not validate_basic_auth(auth_header):
        logger.warning("Webhook authentication failed")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "Unauthorized"},
        )

    # Parse payload
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        logger.exception("Failed to parse webhook payload")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid JSON"},
        )

    # Validate eventType
    event_type: str | None = payload.get("eventType")
    if not event_type:
        logger.warning("Webhook missing eventType: %s", payload)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing eventType"},
        )

    # Validate accountId
    account_id: int | None = payload.get("accountId")
    if not account_id:
        logger.warning("Webhook missing accountId: eventType=%s", event_type)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing accountId"},
        )

    # Verify account exists and is active (uses in-memory cache + lazy load)
    with engine.connect() as conn:
        if not validate_account(account_id, conn):
            logger.warning("Webhook for unknown/inactive account: %s", account_id)
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": f"Account {account_id} not found"},
            )

    # Route to appropriate handler
    event_handlers = {
        "reservation.created": handle_reservation_created,
        "reservation.updated": handle_reservation_updated,
        "message.received": handle_message_received,
    }

    handler = event_handlers.get(event_type)
    if handler:
        try:
            handler(account_id, payload)
            logger.info(
                "Webhook processed successfully: eventType=%s, account=%s",
                event_type,
                account_id,
            )
        except Exception:
            logger.exception(
                "Failed to process webhook: eventType=%s, account=%s",
                event_type,
                account_id,
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Internal server error"},
            )
    else:
        logger.warning("Unsupported event type: %s", event_type)
        # Return 200 anyway - don't fail on unknown events

    return JSONResponse(content={"status": "accepted"})
