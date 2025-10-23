import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

import structlog

from sync_hostaway.config import DEBUG
from sync_hostaway.utils.datetime import utc_now

logger = structlog.get_logger(__name__)


def normalize_raw_messages(raw_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group raw Hostaway messages into threads per reservation, sorted by time.

    Each output item represents a full message thread for a reservation.

    Args:
        raw_messages: List of raw Hostaway message dicts from API.

    Returns:
        List of dicts with:
            - reservation_id
            - listing_id
            - messages (JSON array sorted oldest to newest)
            - created_at
            - updated_at
    """
    threads = defaultdict(list)

    for msg in raw_messages:
        reservation_id = msg.get("reservationId")
        account_id = msg.get("accountId")
        if not reservation_id or not account_id:
            continue  # Skip if key metadata missing

        # Determine timestamp
        sent_at = (
            msg.get("sentChannelDate")
            or msg.get("date")
            or msg.get("insertedOn")
            or msg.get("updatedOn")
        )
        if not sent_at:
            continue

        try:
            sent_at_dt = datetime.fromisoformat(sent_at)
        except ValueError:
            continue

        message_obj = {
            "sent_at": sent_at_dt.isoformat(),
            "sender": "them" if msg.get("isIncoming") else "us",
            "body": msg.get("body") or "",
            "conversation_id": msg.get("conversationId"),
            "listing_id": msg.get("listingMapId"),
        }

        threads[(reservation_id)].append(message_obj)

    # Construct final grouped output
    normalized_threads = []
    now = utc_now().isoformat()

    for (reservation_id), messages in threads.items():
        # Sort by sent_at timestamp (guaranteed to be str from message_obj construction)
        sorted_messages = sorted(messages, key=lambda m: str(m["sent_at"]))
        normalized_threads.append(
            {
                "reservation_id": reservation_id,
                "account_id": account_id,
                "raw_messages": sorted_messages,
                "created_at": now,
                "updated_at": now,
            }
        )

    if DEBUG:
        logger.info(
            "Sample message thread to insert %s",
            json.dumps(normalized_threads[0], default=str, indent=2),
        )

    return normalized_threads
