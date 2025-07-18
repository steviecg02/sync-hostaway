from typing import cast

from sqlalchemy.engine import Engine

from sync_hostaway.db.writers.messages import insert_messages


def test_insert_messages_stub() -> None:
    fake_engine = cast(Engine, object())
    fake_data = [{"id": 201, "conversationId": 88, "body": "Hello there"}]

    # Stub call - replace with real DB logic later
    insert_messages(data=fake_data, engine=fake_engine, dry_run=True)
