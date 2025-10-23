import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import structlog

from sync_hostaway.config import DEBUG
from sync_hostaway.metrics import poll_duration, poll_total, records_synced
from sync_hostaway.network.client import fetch_paginated

logger = structlog.get_logger(__name__)


def poll_messages(account_id: int) -> List[Dict[str, Any]]:
    """
    Polls Hostaway API for all conversations and their messages for the given account.
    Returns a flat list of raw message dicts.

    Args:
        account_id (int): Hostaway account ID

    Returns:
        List[Dict]: A flat list of all conversations and messages.
    """
    with poll_duration.labels(account_id=str(account_id), entity_type="messages").time():
        try:
            conversations = fetch_paginated("conversations", account_id=account_id)
            logger.info(f"Found {len(conversations)} conversations [account_id={account_id}]")

            messages = _fetch_all_conversation_messages(conversations, account_id)
            logger.info(f"Fetched {len(messages)} total messages [account_id={account_id}]")

            if DEBUG and messages:
                logger.debug("Sample message:\n%s", json.dumps(messages[0], indent=2))

            # Record metrics
            records_synced.labels(account_id=str(account_id), entity_type="messages").inc(
                len(messages)
            )
            poll_total.labels(
                account_id=str(account_id), entity_type="messages", status="success"
            ).inc()

            return messages
        except Exception:
            poll_total.labels(
                account_id=str(account_id), entity_type="messages", status="failure"
            ).inc()
            raise


def _fetch_all_conversation_messages(
    conversations: List[Dict[str, Any]], account_id: int
) -> List[Dict[str, Any]]:
    """
    Fetch all messages for each conversation using concurrent requests.

    For each conversation in the list, this function builds the
    `/conversations/{id}/messages` endpoint and uses the paginated fetch client
    to retrieve all messages (across all pages) for that conversation.

    Args:
        conversations (List[Dict]): A list of raw Hostaway conversation objects,
            each containing an "id" field.
        account_id (int): Hostaway account ID

    Returns:
        List[Dict]: A flat list of all message dicts across all conversations.
    """
    all_messages = []

    def fetch(convo: Dict[str, Any]) -> List[Dict[str, Any]]:
        convo_id = convo["id"]
        endpoint = f"conversations/{convo_id}/messages"
        return fetch_paginated(endpoint, account_id=account_id)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, convo) for convo in conversations]
        for future in as_completed(futures):
            all_messages.extend(future.result())

    return all_messages
