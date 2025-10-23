"""
Integration tests for /api/v1/hostaway/accounts endpoints.

Tests account CRUD operations (POST, PATCH, DELETE) with real database.
"""

from typing import Any, Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from sync_hostaway.main import app
from sync_hostaway.models.base import Base


@pytest.fixture(scope="module")
def test_engine() -> Generator[Engine, None, None]:
    """Create a test database engine."""
    # Use a test database
    db_url = "postgresql://postgres:postgres@localhost:5432/postgres"
    engine = create_engine(db_url)

    # Create tables
    Base.metadata.create_all(engine)

    yield engine

    # Cleanup: Drop test data
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM hostaway.accounts WHERE account_id >= 90000"))


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client."""
    return TestClient(app)


@patch("sync_hostaway.routes.accounts.sync_account")
def test_create_account(mock_sync: Any, client: TestClient, test_engine: Engine) -> None:
    """Test POST /api/v1/hostaway/accounts creates a new account."""
    response = client.post(
        "/api/v1/hostaway/accounts",
        json={
            "account_id": 99999,
            "client_secret": "test-secret-123",
        },
    )

    assert response.status_code == 201
    assert "message" in response.json()
    assert "Account created" in response.json()["message"]

    # Verify account exists in database
    with test_engine.connect() as conn:
        result = conn.execute(
            text("SELECT account_id, client_secret FROM hostaway.accounts WHERE account_id = 99999")
        ).fetchone()

        assert result is not None
        assert result[0] == 99999
        assert result[1] == "test-secret-123"


@patch("sync_hostaway.routes.accounts.sync_account")
def test_create_duplicate_account_fails(mock_sync: Any, client: TestClient) -> None:
    """Test POST /api/v1/hostaway/accounts fails for duplicate account_id."""
    # Create first account
    response1 = client.post(
        "/api/v1/hostaway/accounts",
        json={
            "account_id": 99998,
            "client_secret": "test-secret-456",
        },
    )
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = client.post(
        "/api/v1/hostaway/accounts",
        json={
            "account_id": 99998,
            "client_secret": "different-secret",
        },
    )

    assert response2.status_code == 422
    assert "already exists" in response2.json()["detail"]


@patch("sync_hostaway.routes.accounts.sync_account")
def test_update_account(mock_sync: Any, client: TestClient, test_engine: Engine) -> None:
    """Test PATCH /api/v1/hostaway/accounts updates account credentials."""
    # Create account first
    client.post(
        "/api/v1/hostaway/accounts",
        json={
            "account_id": 99997,
            "client_secret": "original-secret",
        },
    )

    # Update it
    response = client.patch(
        "/api/v1/hostaway/accounts/99997",
        json={
            "client_secret": "updated-secret",
        },
    )

    assert response.status_code == 200
    assert "updated" in response.json()["message"].lower()

    # Verify update in database
    with test_engine.connect() as conn:
        result = conn.execute(
            text("SELECT client_secret FROM hostaway.accounts WHERE account_id = 99997")
        ).fetchone()

        assert result is not None
        assert result[0] == "updated-secret"


@patch("sync_hostaway.routes.accounts.sync_account")
def test_soft_delete_account(mock_sync: Any, client: TestClient, test_engine: Engine) -> None:
    """Test DELETE /api/v1/hostaway/accounts with soft=true deactivates account."""
    # Create account
    client.post(
        "/api/v1/hostaway/accounts",
        json={
            "account_id": 99996,
            "client_secret": "test-secret",
        },
    )

    # Soft delete
    response = client.delete("/api/v1/hostaway/accounts/99996?soft=true")

    assert response.status_code == 200
    assert "deactivated" in response.json()["message"].lower()

    # Verify account still exists but is_active=false
    with test_engine.connect() as conn:
        result = conn.execute(
            text("SELECT is_active FROM hostaway.accounts WHERE account_id = 99996")
        ).fetchone()

        assert result is not None
        assert result[0] is False


@patch("sync_hostaway.routes.accounts.sync_account")
def test_hard_delete_account(mock_sync: Any, client: TestClient, test_engine: Engine) -> None:
    """Test DELETE /api/v1/hostaway/accounts with soft=false permanently deletes account."""
    # Create account
    client.post(
        "/api/v1/hostaway/accounts",
        json={
            "account_id": 99995,
            "client_secret": "test-secret",
        },
    )

    # Hard delete
    response = client.delete("/api/v1/hostaway/accounts/99995?soft=false")

    assert response.status_code == 200
    assert "permanently deleted" in response.json()["message"].lower()

    # Verify account is gone
    with test_engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM hostaway.accounts WHERE account_id = 99995")
        ).fetchone()

        assert result is None
