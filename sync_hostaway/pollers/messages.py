import concurrent.futures
import json
import logging
import time
from typing import Dict, List
from urllib.parse import urljoin

import requests

from sync_hostaway.config import DEBUG
from sync_hostaway.hostaway_api.auth import get_access_token
from sync_hostaway.hostaway_api.client import fetch_paginated

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hostaway.com/v1/"


def poll_messages() -> List[Dict]:
    """
    Polls Hostaway API for all conversations and their messages.
    Returns a flat list of raw message dicts.
    """
    token = get_access_token()

    conversations = fetch_paginated("conversations", token)
    logger.info(f"Found {len(conversations)} conversations")

    messages = _fetch_all_conversation_messages(conversations, token)
    logger.info(f"Fetched {len(messages)} total messages")

    if DEBUG and messages:
        logger.debug("Sample message:\n%s", json.dumps(messages[0], indent=2))

    return messages


def _fetch_all_conversation_messages(conversations: List[Dict], token: str) -> List[Dict]:
    """
    Fetches messages for all conversations using thread pool.
    """
    all_messages = []

    def fetch_messages_for_convo(convo: Dict) -> List[Dict]:
        convo_id = convo["id"]
        url = urljoin(BASE_URL, f"conversations/{convo_id}/messages")
        page = 1
        messages = []

        while True:
            res = requests.get(
                url, headers={"Authorization": f"Bearer {token}"}, params={"page": page}
            )

            if res.status_code == 429:
                logger.warning(f"Rate limited on convo {convo_id}. Sleeping...")
                time.sleep(min(60, 2**page))
                continue

            res.raise_for_status()
            data = res.json()

            page_messages = data.get("result", [])
            messages.extend(page_messages)

            total_pages = data.get("totalPages", 1)
            logger.debug(
                "Convo %s: page %s/%s, %s messages",
                convo_id,
                page,
                total_pages,
                len(page_messages),
            )

            if page >= total_pages:
                break

            page += 1

        return messages

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_messages_for_convo, convo) for convo in conversations]
        for future in concurrent.futures.as_completed(futures):
            all_messages.extend(future.result())

    return all_messages
