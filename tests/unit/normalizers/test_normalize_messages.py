from sync_hostaway.normalizers.messages import normalize_raw_messages


def test_normalize_raw_messages_single_thread() -> None:
    raw_input = [
        {
            "reservationId": 45054652,
            "listingMapId": "abc-123",
            "conversationId": 999,
            "isIncoming": 1,
            "body": "Test message from guest",
            "date": "2025-07-16T18:31:12",
        },
        {
            "reservationId": 45054652,
            "listingMapId": "abc-123",
            "conversationId": 999,
            "isIncoming": 0,
            "body": "Reply from host",
            "sentChannelDate": "2025-07-16T19:30:00",
        },
    ]

    result = normalize_raw_messages(raw_input)
    assert len(result) == 1
    thread = result[0]
    assert thread["reservation_id"] == 45054652
    assert len(thread["raw_messages"]) == 2
    assert thread["raw_messages"][0]["sender"] == "them"
    assert thread["raw_messages"][1]["sender"] == "us"
    assert thread["raw_messages"][0]["body"] == "Test message from guest"
    assert "created_at" in thread
    assert "updated_at" in thread

    # Ensure sorted
    assert thread["raw_messages"][0]["sent_at"] < thread["raw_messages"][1]["sent_at"]
