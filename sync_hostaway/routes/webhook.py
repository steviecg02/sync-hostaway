"""Hostaway webhook receiver route."""

import base64
from typing import Any

import structlog
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from sync_hostaway.config import WEBHOOK_PASSWORD, WEBHOOK_USERNAME
from sync_hostaway.db.engine import engine
from sync_hostaway.db.writers.reservations import insert_reservations
from sync_hostaway.services.account_cache import validate_account

router = APIRouter()
logger = structlog.get_logger(__name__)


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
    try:
        reservation_data = payload.get("data", {})
        if not reservation_data:
            logger.warning(
                "reservation_missing_data",
                event_type="reservation.created",
                account_id=account_id,
                full_payload=payload,
            )
            return

        insert_reservations(engine, account_id, [reservation_data])

        # Log success with key identifiers only
        logger.info(
            "reservation_created",
            account_id=account_id,
            reservation_id=reservation_data.get("id"),
            listing_id=reservation_data.get("listingMapId"),
            guest_name=reservation_data.get("guestName"),
            status=reservation_data.get("status"),
        )
    except Exception as e:
        logger.error(
            "reservation_processing_failed",
            event_type="reservation.created",
            account_id=account_id,
            error=str(e),
            full_payload=payload,
        )
        raise


def handle_reservation_updated(account_id: int, payload: dict[str, Any]) -> None:
    """
    Handle reservation.updated webhook event.

    Args:
        account_id: Hostaway account ID
        payload: Webhook payload containing reservation data
    """
    try:
        reservation_data = payload.get("data", {})
        if not reservation_data:
            logger.warning(
                "reservation_missing_data",
                event_type="reservation.updated",
                account_id=account_id,
                full_payload=payload,
            )
            return

        insert_reservations(engine, account_id, [reservation_data])

        # Log success with key identifiers only
        logger.info(
            "reservation_updated",
            account_id=account_id,
            reservation_id=reservation_data.get("id"),
            listing_id=reservation_data.get("listingMapId"),
            guest_name=reservation_data.get("guestName"),
            status=reservation_data.get("status"),
        )
    except Exception as e:
        logger.error(
            "reservation_processing_failed",
            event_type="reservation.updated",
            account_id=account_id,
            error=str(e),
            full_payload=payload,
        )
        raise


def handle_message_received(account_id: int, payload: dict[str, Any]) -> None:
    """
    Handle message.received webhook event.

    TODO: Implement full conversation fetching logic.
    For now, this is a stub that logs key message identifiers
    so we can track message events without persisting them.

    Args:
        account_id: Hostaway account ID
        payload: Webhook payload containing message data
    """
    try:
        message_data = payload.get("data", {})
        if not message_data:
            logger.warning(
                "message_missing_data",
                account_id=account_id,
                full_payload=payload,
            )
            return

        # Extract key identifiers from message data
        conversation_id = message_data.get("conversationId")
        message_id = message_data.get("id")
        reservation_id = message_data.get("reservationId")
        listing_id = message_data.get("listingMapId")
        body = message_data.get("body", "")
        is_incoming = message_data.get("isIncoming", 0)

        # Truncate body for preview (first 50 chars)
        body_preview = (body[:50] + "...") if len(body) > 50 else body
        direction = "incoming" if is_incoming == 1 else "outgoing"

        logger.info(
            "message_received_stub",
            account_id=account_id,
            conversation_id=conversation_id,
            message_id=message_id,
            reservation_id=reservation_id,
            listing_id=listing_id,
            direction=direction,
            body_preview=body_preview,
            note="Message logged but not persisted (stub)",
        )
    except Exception as e:
        logger.error(
            "message_parsing_failed",
            account_id=account_id,
            error=str(e),
            full_payload=payload,
        )
        raise

    # TODO: Implement persistence
    # conversation_id = payload.get("data", {}).get("conversationId")
    # if conversation_id:
    #     conversation = fetch_conversation(account_id, conversation_id)
    #     normalized = normalize_raw_messages([conversation])
    #     insert_messages(engine, account_id, normalized)


@router.post("/webhooks")
async def receive_hostaway_webhook(request: Request) -> JSONResponse:
    """
    Handle incoming Hostaway webhook events.

    Supports only 3 event types:
    - reservation.created
    - reservation.updated
    - message.received

    Authentication: HTTP Basic Auth with global WEBHOOK_USERNAME/WEBHOOK_PASSWORD

    Expected payload structure from Hostaway:
        {
            "object": "reservation",
            "event": "reservation.updated",
            "accountId": 59808,
            "payload": {
                "data": {...}
            }
        }

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

    # Log incoming webhook with minimal info
    logger.info(
        "webhook_received",
        event_type=payload.get("event") or payload.get("eventType"),
        account_id=payload.get("accountId"),
        object_type=payload.get("object"),
    )

    # Validate event field (Hostaway uses "event" not "eventType")
    event_type: str | None = payload.get("event") or payload.get("eventType")
    if not event_type:
        logger.warning("webhook_missing_event_type", payload=payload)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing event or eventType field"},
        )

    # Validate accountId
    account_id: int | None = payload.get("accountId")
    if not account_id:
        logger.warning("Webhook missing accountId: event=%s", event_type)
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

    # Normalize payload structure (Hostaway uses nested payload.data)
    # Transform: {"payload": {"data": {...}}} -> {"data": {...}}
    normalized_payload = payload
    if "payload" in payload and "data" in payload["payload"]:
        normalized_payload = payload["payload"]
        logger.debug(
            "webhook_normalized_payload",
            event_type=event_type,
            account_id=account_id,
            original_structure="nested_payload",
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
            handler(account_id, normalized_payload)
            # Handler-specific logs already indicate success
        except Exception as e:
            logger.exception(
                "webhook_processing_failed",
                event_type=event_type,
                account_id=account_id,
                error=str(e),
                payload=payload,
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Internal server error"},
            )
    else:
        logger.warning(
            "webhook_unsupported_event_type",
            event_type=event_type,
            account_id=account_id,
            payload=payload,
        )
        # Return 200 anyway - don't fail on unknown events

    return JSONResponse(content={"status": "accepted"})
