import sys
from pathlib import Path
from typing import Any, Union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
from typing import Optional

from dotenv import load_dotenv

from sync_hostaway.network.client import fetch_page, fetch_paginated
from sync_hostaway.pollers.messages import poll_messages

load_dotenv()

# === TOKEN LOADER ===


def get_token_for_account(account_id: Optional[str] = None) -> str:
    if account_id:
        raise NotImplementedError(f"Multi-tenant lookup for {account_id} not yet implemented.")
    token = os.getenv("HOSTAWAY_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("HOSTAWAY_ACCESS_TOKEN not set in .env")
    return token


# === FIXTURE FETCH + SAVE ===


def save_fixture(data: Union[dict[str, object], list[dict[str, object]]], filename: str) -> None:
    os.makedirs("tests/fixtures", exist_ok=True)
    path = f"tests/fixtures/{filename}"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Saved {filename} ({len(data) if isinstance(data, list) else 'dict'})")


# === Fetch and save both versions ===


def save_endpoint_fixtures(endpoint: str, prefix: str, token: str) -> dict[str, Any]:
    page0 = fetch_page(endpoint, token, page_number=0)
    save_fixture(page0, f"{prefix}_page_0.json")

    all_data = fetch_paginated(endpoint, token)
    save_fixture(all_data, f"{prefix}_paginated.json")

    return page0


# === Master fetch ===


def fetch_all_fixtures(token: str) -> None:
    save_endpoint_fixtures("listings", "hostaway_listings", token)
    save_endpoint_fixtures("reservations", "hostaway_reservations", token)

    convo_page0 = save_endpoint_fixtures("conversations", "hostaway_conversations", token)

    # 🔁 Grab first conversation ID and fetch page 1 of its messages
    conversations = convo_page0.get("result", [])
    if conversations:
        convo_id = conversations[0]["id"]
        endpoint = f"conversations/{convo_id}/messages"
        print(f"📨 Fetching page 1 of messages for conversation {convo_id}")
        page_data = fetch_page(endpoint=endpoint, token=token, page_number=1)
        save_fixture(page_data, "hostaway_messages_page_0.json")
    else:
        print("⚠️ No conversations found to sample messages from.")

    save_fixture(poll_messages(), "hostaway_messages_paginated.json")


# === CLI ===

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and save Hostaway API fixtures.")
    parser.add_argument("--account", help="Account ID for future multi-tenant mode (optional)")
    args = parser.parse_args()

    token = get_token_for_account(args.account)
    fetch_all_fixtures(token)
