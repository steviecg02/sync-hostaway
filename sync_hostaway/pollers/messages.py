import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from sync_hostaway.config import DEBUG
from sync_hostaway.network.auth import get_access_token
from sync_hostaway.network.client import fetch_paginated

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hostaway.com/v1/"


def poll_messages() -> List[Dict[str, Any]]:
    """
    Polls Hostaway API for all conversations and their messages.
    Returns a flat list of raw message dicts.

    Returns:
        List[Dict]: A flat list of all mconversations.
    """
    token = get_access_token()

    conversations = fetch_paginated("conversations", token)
    logger.info(f"Found {len(conversations)} conversations")

    messages = _fetch_all_conversation_messages(conversations, token)
    logger.info(f"Fetched {len(messages)} total messages")

    if DEBUG and messages:
        logger.debug("Sample message:\n%s", json.dumps(messages[0], indent=2))

    return messages


def _fetch_all_conversation_messages(
    conversations: List[Dict[str, Any]], token: str
) -> List[Dict[str, Any]]:
    """
    Fetch all messages for each conversation using concurrent requests.

    For each conversation in the list, this function builds the
    `/conversations/{id}/messages` endpoint and uses the paginated fetch client
    to retrieve all messages (across all pages) for that conversation.

    All conversations are processed concurrently, while pagination within
    each conversation is handled sequentially by `fetch_paginated()`.

    Args:
        conversations (List[Dict]): A list of raw Hostaway conversation objects,
            each containing an "id" field.
        token (str): Hostaway API bearer token.

    Returns:
        List[Dict]: A flat list of all message dicts across all conversations.
    """
    all_messages = []

    def fetch(convo: Dict[str, Any]) -> List[Dict[str, Any]]:
        convo_id = convo["id"]
        endpoint = f"conversations/{convo_id}/messages"
        return fetch_paginated(endpoint, token)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, convo) for convo in conversations]
        for future in as_completed(futures):
            all_messages.extend(future.result())

    return all_messages
