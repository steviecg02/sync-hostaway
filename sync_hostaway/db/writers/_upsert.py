"""
Generic upsert helper with IS DISTINCT FROM optimization.

This module provides a reusable upsert function that eliminates duplication
across listings, reservations, and messages writers. It implements the
IS DISTINCT FROM pattern to prevent unnecessary writes when data hasn't changed.
"""

from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection


def upsert_with_distinct_check(
    conn: Connection,
    table: type,
    rows: list[dict[str, Any]],
    conflict_column: str,
    distinct_column: str = "raw_payload",
    update_columns: list[str] | None = None,
) -> None:
    """
    Perform upsert with IS DISTINCT FROM optimization.

    Only updates rows where the distinct_column value has actually changed,
    preventing unnecessary writes and updated_at timestamp changes. This is
    critical for performance and avoiding spurious "updated" records.

    Args:
        conn: Active database connection (within transaction)
        table: SQLAlchemy ORM table class (e.g., Listing, Reservation)
        rows: List of row dicts to upsert
        conflict_column: Column name for ON CONFLICT (usually "id")
        distinct_column: Column to check for changes (default: "raw_payload")
        update_columns: Columns to update on conflict (default: [distinct_column, "updated_at"])

    Example:
        >>> with engine.begin() as conn:
        ...     upsert_with_distinct_check(
        ...         conn=conn,
        ...         table=Listing,
        ...         rows=[{"id": 1, "raw_payload": {...}, ...}],
        ...         conflict_column="id",
        ...     )

    Technical Details:
        - Uses PostgreSQL's ON CONFLICT DO UPDATE
        - IS DISTINCT FROM checks NULL-safe equality
        - Only writes if data actually changed (optimization)
        - Prevents updated_at from changing on no-op updates
    """
    if not rows:
        return

    if update_columns is None:
        update_columns = [distinct_column, "updated_at"]

    stmt = insert(table).values(rows)

    # Build set_ dict dynamically from update_columns
    set_dict = {col: getattr(stmt.excluded, col) for col in update_columns}

    # Build IS DISTINCT FROM check for the distinct_column
    distinct_check = getattr(table, distinct_column).is_distinct_from(
        getattr(stmt.excluded, distinct_column)
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=[conflict_column],
        set_=set_dict,
        where=distinct_check,
    )

    conn.execute(stmt)
