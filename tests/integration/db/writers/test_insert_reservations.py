from typing import cast

from sqlalchemy.engine import Engine

from sync_hostaway.db.writers.reservations import insert_reservations


def test_insert_reservations_stub() -> None:
    fake_engine = cast(Engine, object())
    fake_data = [{"id": 101, "listingMapId": 1, "guestName": "Test Guest"}]

    # Stub call - replace with real DB logic later
    insert_reservations(data=fake_data, engine=fake_engine, dry_run=True)
