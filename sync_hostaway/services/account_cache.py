"""
In-memory cache for active account IDs.

This module provides a fast lookup mechanism for validating account IDs
in webhook requests without hitting the database every time.

Strategy:
- Load all active account IDs on startup
- Lazy-load new accounts when encountered (query once, cache forever)
- Thread-safe operations using threading.Lock
"""

import logging
import threading

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from sync_hostaway.models.accounts import Account

logger = logging.getLogger(__name__)

# In-memory cache of active account IDs (thread-safe)
_active_account_ids: set[int] = set()
_cache_lock = threading.Lock()


def refresh_account_cache(engine: Engine) -> None:
    """
    Refresh the in-memory cache with all active account IDs from database.

    This should be called on application startup to populate the cache.

    Args:
        engine: SQLAlchemy engine for database connection
    """
    global _active_account_ids

    with engine.connect() as conn:
        result = conn.execute(
            select(Account.account_id).where(Account.is_active == True)  # noqa: E712
        )
        account_ids = {row[0] for row in result}

    with _cache_lock:
        _active_account_ids = account_ids

    logger.info("Account cache refreshed: %d active accounts loaded", len(account_ids))


def is_account_cached(account_id: int) -> bool:
    """
    Check if account_id exists in the in-memory cache (fast lookup).

    Args:
        account_id: Hostaway account ID to check

    Returns:
        bool: True if account is in cache, False otherwise
    """
    with _cache_lock:
        return account_id in _active_account_ids


def add_account_to_cache(account_id: int, conn: Connection) -> bool:
    """
    Query database for account and add to cache if it exists and is active.

    This implements lazy loading - when we encounter a new account_id
    not in the cache, we query once and cache the result.

    Args:
        account_id: Hostaway account ID to query and cache
        conn: SQLAlchemy connection for database query

    Returns:
        bool: True if account exists and is active, False otherwise
    """
    global _active_account_ids

    # Query database to check if account exists and is active
    result = conn.execute(
        select(Account.account_id)
        .where(Account.account_id == account_id)
        .where(Account.is_active == True)  # noqa: E712
    ).fetchone()

    if result:
        # Account exists and is active - add to cache
        with _cache_lock:
            _active_account_ids.add(account_id)
        logger.info("Account %d added to cache (lazy load)", account_id)
        return True
    else:
        # Account doesn't exist or is inactive
        logger.warning("Account %d not found or inactive (not cached)", account_id)
        return False


def validate_account(account_id: int, conn: Connection) -> bool:
    """
    Validate that an account exists and is active.

    Uses two-tier strategy:
    1. Check in-memory cache first (O(1) lookup)
    2. If not found, query database and cache if exists (lazy load)

    Args:
        account_id: Hostaway account ID to validate
        conn: SQLAlchemy connection for database query (only used on cache miss)

    Returns:
        bool: True if account exists and is active, False otherwise
    """
    # Fast path: Check cache first
    if is_account_cached(account_id):
        return True

    # Slow path: Query database and cache result
    return add_account_to_cache(account_id, conn)


def remove_account_from_cache(account_id: int) -> None:
    """
    Remove an account from the cache (e.g., when account is soft/hard deleted).

    Args:
        account_id: Hostaway account ID to remove
    """
    global _active_account_ids

    with _cache_lock:
        _active_account_ids.discard(account_id)

    logger.info("Account %d removed from cache", account_id)


def get_cache_size() -> int:
    """
    Get the current number of accounts in the cache.

    Returns:
        int: Number of cached account IDs
    """
    with _cache_lock:
        return len(_active_account_ids)
