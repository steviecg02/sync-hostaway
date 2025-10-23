"""
FastAPI dependency injection providers.

This module contains dependency providers for FastAPI routes, enabling better
testability through dependency injection and following FastAPI best practices.

Dependencies can be overridden in tests using app.dependency_overrides, making
it easy to inject mock objects for isolated unit testing.
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy.engine import Engine

from sync_hostaway.db.engine import engine


def get_db_engine() -> Generator[Engine, None, None]:
    """
    Provide database engine for dependency injection.

    This dependency yields the SQLAlchemy engine instance for use in route
    handlers. Using dependency injection instead of direct imports improves
    testability and follows FastAPI conventions.

    Yields:
        Engine: SQLAlchemy database engine

    Example:
        >>> from fastapi import Depends
        >>> from sync_hostaway.dependencies import get_db_engine
        >>>
        >>> @router.post("/accounts")
        >>> def create_account(
        ...     payload: AccountCreatePayload,
        ...     engine: Engine = Depends(get_db_engine),
        ... ):
        ...     with engine.begin() as conn:
        ...         # Use engine for database operations
        ...         ...

    Testing Example:
        >>> from unittest.mock import Mock
        >>> from fastapi.testclient import TestClient
        >>>
        >>> # Override dependency in tests
        >>> mock_engine = Mock(spec=Engine)
        >>> app.dependency_overrides[get_db_engine] = lambda: mock_engine
        >>>
        >>> client = TestClient(app)
        >>> response = client.post("/accounts", json={...})
        >>>
        >>> # Verify mock was called
        >>> mock_engine.begin.assert_called_once()
    """
    yield engine
