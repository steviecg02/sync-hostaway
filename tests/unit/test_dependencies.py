"""
Unit tests for FastAPI dependency injection.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from sync_hostaway.dependencies import get_db_engine


@pytest.fixture
def app_with_di() -> FastAPI:
    """Create FastAPI app with dependency injection for testing."""
    app = FastAPI()

    @app.get("/test-db")
    def test_db_endpoint(engine: Engine = Depends(get_db_engine)) -> dict[str, str]:
        """Test endpoint that uses database engine via DI."""
        # Simulate using the engine
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")  # type: ignore
            return {"status": "connected", "result": str(result)}

    return app


@pytest.mark.unit
def test_get_db_engine_dependency() -> None:
    """Test that get_db_engine returns the engine instance."""
    engine_gen = get_db_engine()
    engine = next(engine_gen)

    assert engine is not None
    assert isinstance(engine, Engine)


@pytest.mark.unit
def test_dependency_injection_can_be_overridden() -> None:
    """Test that dependency can be overridden for testing."""
    app = FastAPI()

    @app.get("/test")
    def test_endpoint(engine: Engine = Depends(get_db_engine)) -> dict[str, str]:
        """Test endpoint."""
        return {"engine_name": engine.name}

    # Create mock engine
    mock_engine = Mock(spec=Engine)
    mock_engine.name = "mock_engine"

    # Override dependency
    app.dependency_overrides[get_db_engine] = lambda: mock_engine

    # Test with overridden dependency
    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200
    assert response.json() == {"engine_name": "mock_engine"}


@pytest.mark.unit
def test_dependency_injection_provides_same_engine() -> None:
    """Test that multiple calls get the same engine instance."""
    engine1_gen = get_db_engine()
    engine1 = next(engine1_gen)

    engine2_gen = get_db_engine()
    engine2 = next(engine2_gen)

    # Should be the same singleton instance
    assert engine1 is engine2
