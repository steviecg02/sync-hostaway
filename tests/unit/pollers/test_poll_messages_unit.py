import json
from unittest.mock import MagicMock, patch

from sync_hostaway.pollers.messages import _fetch_all_conversation_messages, poll_messages

DUMMY_CONVERSATIONS = [{"id": 1}, {"id": 2}]
DUMMY_MESSAGES = [{"id": 101}, {"id": 102}]


@patch("sync_hostaway.pollers.messages._fetch_all_conversation_messages")
@patch("sync_hostaway.pollers.messages.fetch_paginated")
@patch("sync_hostaway.pollers.messages.get_access_token")
def test_poll_messages_returns_flat_messages(
    mock_get_token: MagicMock,
    mock_fetch_convos: MagicMock,
    mock_fetch_msgs: MagicMock,
) -> None:
    """Test poll_messages returns flattened list from mocked responses."""
    mock_get_token.return_value = "mock-token"
    mock_fetch_convos.return_value = DUMMY_CONVERSATIONS
    mock_fetch_msgs.return_value = DUMMY_MESSAGES

    result = poll_messages()

    assert result == DUMMY_MESSAGES
    mock_get_token.assert_called_once()
    mock_fetch_convos.assert_called_once_with("conversations", "mock-token")
    mock_fetch_msgs.assert_called_once_with(DUMMY_CONVERSATIONS, "mock-token")


@patch("sync_hostaway.pollers.messages.logger")
@patch("sync_hostaway.pollers.messages._fetch_all_conversation_messages")
@patch("sync_hostaway.pollers.messages.fetch_paginated")
@patch("sync_hostaway.pollers.messages.get_access_token")
@patch("sync_hostaway.pollers.messages.DEBUG", True)
def test_poll_messages_logs_sample_message(
    mock_token: MagicMock,
    mock_fetch_convos: MagicMock,
    mock_fetch_msgs: MagicMock,
    mock_logger: MagicMock,
) -> None:
    """
    Test that poll_messages logs a sample message when DEBUG is True.
    """
    mock_token.return_value = "mock-token"
    mock_fetch_convos.return_value = [{"id": 1}]
    mock_fetch_msgs.return_value = [{"id": 999, "body": "Hello"}]

    poll_messages()

    mock_logger.debug.assert_any_call(
        "Sample message:\n%s", json.dumps({"id": 999, "body": "Hello"}, indent=2)
    )


@patch("sync_hostaway.pollers.messages.fetch_paginated")
def test__fetch_all_conversation_messages_makes_expected_calls(mock_fetch: MagicMock) -> None:
    """Test _fetch_all_conversation_messages calls fetch_paginated once per conversation."""
    mock_fetch.side_effect = [[{"id": "m1"}], [{"id": "m2"}]]
    result = _fetch_all_conversation_messages(DUMMY_CONVERSATIONS, token="abc123")

    assert result == [{"id": "m1"}, {"id": "m2"}]
    assert mock_fetch.call_count == 2
    mock_fetch.assert_any_call("conversations/1/messages", "abc123")
    mock_fetch.assert_any_call("conversations/2/messages", "abc123")
