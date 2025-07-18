import pytest

from sync_hostaway.network.auth import get_access_token
from sync_hostaway.network.client import fetch_page

# === Config ===

REQUIRED_LISTING_KEYS: set[str] = set()  # Add when known
REQUIRED_RESERVATION_KEYS: set[str] = set()  # Add when known
REQUIRED_CONVERSATION_KEYS: set[str] = set()  # Add when known
REQUIRED_MESSAGE_KEYS: set[str] = set()  # Add when known

ENDPOINTS = ["listings", "reservations", "conversations"]

# === Fixtures ===


@pytest.fixture(scope="module")
def token() -> str:
    """Fixture to retrieve Hostaway API token once per test module."""
    return get_access_token()


# === Sanity Check: General Structure ===


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_hostaway_endpoint_returns_expected_structure(endpoint: str, token: str) -> None:
    """
    Hits the first page of each core endpoint and validates standard structure.
    """
    page_data = fetch_page(endpoint, token=token, page_number=0)

    assert isinstance(page_data, dict)
    assert "result" in page_data
    assert "count" in page_data
    assert "limit" in page_data

    assert isinstance(page_data["result"], list)
    assert isinstance(page_data["count"], int)
    assert isinstance(page_data["limit"], int)


# === Schema Check: Per Object Type ===


def test_listings_structure(token: str) -> None:
    """
    Validates that each listing includes the expected keys.
    """
    listings = fetch_page("listings", token=token)["result"]
    assert listings, "No listings returned."
    for obj in listings:
        missing = REQUIRED_LISTING_KEYS - obj.keys()
        assert not missing, f"Missing listing keys: {missing}"


def test_reservations_structure(token: str) -> None:
    """
    Validates that each reservation includes the expected keys.
    """
    reservations = fetch_page("reservations", token=token)["result"]
    assert reservations, "No reservations returned."
    for obj in reservations:
        missing = REQUIRED_RESERVATION_KEYS - obj.keys()
        assert not missing, f"Missing reservation keys: {missing}"


def test_conversations_structure(token: str) -> None:
    """
    Validates that each conversation includes the expected keys.
    """
    conversations = fetch_page("conversations", token=token)["result"]
    assert conversations, "No conversations returned."
    for obj in conversations:
        missing = REQUIRED_CONVERSATION_KEYS - obj.keys()
        assert not missing, f"Missing conversation keys: {missing}"


def test_conversation_messages_structure(token: str) -> None:
    """
    Fetches first conversation, then validates first page of messages.
    """
    conversations = fetch_page("conversations", token=token)["result"]
    assert conversations, "No conversations found to sample."

    convo_id = conversations[0]["id"]
    endpoint = f"conversations/{convo_id}/messages"
    messages = fetch_page(endpoint, token=token)["result"]

    assert messages, f"No messages returned for convo {convo_id}"
    for obj in messages:
        missing = REQUIRED_MESSAGE_KEYS - obj.keys()
        assert not missing, f"Missing message keys: {missing}"
