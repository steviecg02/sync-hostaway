from typing import cast

from sqlalchemy.engine import Engine

from sync_hostaway.db.writers.listings import insert_listings


def test_insert_listings_stub() -> None:
    fake_engine = cast(Engine, object())
    fake_data = [{"id": 1, "name": "Test Listing"}]

    # Stub call - replace with real DB logic later
    insert_listings(data=fake_data, engine=fake_engine, dry_run=True)
