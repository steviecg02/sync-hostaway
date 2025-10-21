# Contributing to sync-hostaway

This guide establishes development standards and workflows for the Hostaway Sync Service. Whether you're fixing a bug, adding a feature, or improving tests, following these guidelines ensures code quality and maintainability.

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Code Standards](#code-standards)
3. [Code Quality Standards](#code-quality-standards)
4. [Architecture Patterns](#architecture-patterns-must-follow)
5. [Testing Requirements](#testing-requirements)
6. [Development Workflow](#development-workflow)
7. [Make Commands Reference](#make-commands-reference)
8. [Pre-Commit Hooks](#pre-commit-hooks)
9. [Troubleshooting](#troubleshooting)

---

## Development Environment Setup

### Prerequisites

- **Python 3.11+** (required by codebase)
- **Docker & Docker Compose** (for local PostgreSQL)
- **Git** with pre-commit support
- **PostgreSQL 15** (if running outside Docker)

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd sync-hostaway

# Create virtual environment
make venv
source venv/bin/activate

# Install all dependencies (production + dev)
make install-dev

# Install pre-commit hooks
pre-commit install

# Verify installation
python --version  # Should be 3.11+
pytest --version
mypy --version
```

### Environment Variables

Create a `.env` file in project root:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres

# Logging
LOG_LEVEL=INFO

# Development
DRY_RUN=false

# CORS (comma-separated origins)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
```

### Local Development with Docker Compose

```bash
# Start PostgreSQL + application
docker-compose up -d

# View logs
docker-compose logs -f app

# Run migrations
docker-compose exec app alembic upgrade head

# Stop services
docker-compose down
```

---

## Code Standards

### Type Hints (REQUIRED)

All functions must have complete type hints. We use Mypy in **strict mode**.

#### Required Patterns

```python
from __future__ import annotations  # Use this for clean forward references

from typing import Any

# ✅ GOOD - Complete type hints
def fetch_data(
    endpoint: str,
    page: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    """Fetch data from API endpoint."""
    ...

# ❌ BAD - Missing return type
def fetch_data(endpoint: str, page: int = 0):
    ...

# ❌ BAD - Missing parameter types
def fetch_data(endpoint, page=0) -> dict:
    ...
```

#### Common Type Patterns

```python
from collections.abc import Callable
from typing import Any, Optional

# Optional values (use | None in Python 3.11+)
def get_token(account_id: int) -> str | None:
    ...

# Dictionaries with unknown structure
def parse_payload(data: dict[str, Any]) -> dict[str, Any]:
    ...

# Lists and sequences
def process_items(items: list[dict[str, Any]]) -> list[int]:
    ...

# Callbacks
def retry_operation(
    operation: Callable[[], dict[str, Any]],
    retries: int = 3,
) -> dict[str, Any]:
    ...

# SQLAlchemy types
from sqlalchemy import Engine
from sqlalchemy.engine import Connection

def insert_data(engine: Engine, data: list[dict[str, Any]]) -> None:
    with engine.begin() as conn:
        ...
```

### Docstrings (REQUIRED - Google Style)

All **public** functions and classes must have docstrings. Use Google style format.

#### Function Docstrings

```python
def fetch_paginated(
    endpoint: str,
    token: str,
    limit: int = 100,
    account_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch all pages of data from a Hostaway API endpoint.

    Automatically handles pagination by fetching the first page to determine
    total count, then fetching remaining pages concurrently.

    Args:
        endpoint: API endpoint path (e.g., "listings" or "reservations")
        token: Bearer token for authentication
        limit: Maximum records per page (default: 100)
        account_id: Hostaway account ID for token refresh on 403 (optional)

    Returns:
        List of all records from all pages combined

    Raises:
        requests.HTTPError: If API returns non-200 status after retries
        requests.Timeout: If request exceeds timeout threshold

    Example:
        >>> listings = fetch_paginated("listings", token, limit=50)
        >>> len(listings)
        237
    """
    ...
```

#### Class Docstrings

```python
class Account(Base):
    """
    ORM model for connected Hostaway accounts.

    Each account is uniquely identified by Hostaway's provided account_id.
    Credentials and tokens are stored per account, with optional webhook auth support.

    Attributes:
        account_id: Hostaway account identifier (primary key)
        customer_id: Internal customer UUID for multi-tenant support
        client_secret: Hostaway OAuth client secret
        access_token: Current valid access token
        is_active: Whether account is enabled for syncing
        last_sync_at: Timestamp of most recent successful sync
    """
    __tablename__ = "accounts"
    ...
```

#### Private Functions

Private functions (prefixed with `_`) may have shorter docstrings:

```python
def _calculate_offset(page: int, limit: int) -> int:
    """Calculate API offset from page number and limit."""
    return page * limit
```

### Code Formatting

We use **Black** (line length 100) and **Ruff** for automated formatting.

```bash
# Format all code (automatic fixes)
make format

# Check formatting without changes
ruff check .
black --check .

# Format specific file
black sync_hostaway/network/client.py
ruff check --fix sync_hostaway/network/client.py
```

**Configuration:** See `pyproject.toml`

- Line length: 100 characters
- Target: Python 3.11
- Ruff rules: E (pycodestyle), F (pyflakes), I (isort)

---

## Code Quality Standards

### Function Design Principles

#### 1. Single Responsibility Principle

Each function should do **one thing** and do it well.

```python
# ✅ GOOD - Single responsibility
def fetch_listings(token: str) -> list[dict[str, Any]]:
    """Fetch listings from API."""
    return fetch_paginated("listings", token)

def insert_listings(engine: Engine, account_id: int, data: list[dict[str, Any]]) -> None:
    """Insert listings into database."""
    # ... database logic only

# ❌ BAD - Multiple responsibilities
def fetch_and_save_listings(engine: Engine, token: str) -> None:
    """Fetch listings and save to database."""  # Does two things!
    data = fetch_paginated("listings", token)  # Network concern
    # ... database logic  # Database concern
```

#### 2. Maximum Complexity

Target: **Cyclomatic complexity < 10**

Ruff automatically checks complexity. If a function is too complex, refactor into smaller functions.

```python
# ✅ GOOD - Low complexity
def should_retry(status_code: int) -> bool:
    """Determine if request should be retried based on status."""
    return status_code == 429 or status_code >= 500

# ❌ BAD - High complexity (nested ifs, multiple branches)
def handle_response(response):
    if response.status_code == 200:
        if response.json():
            if "data" in response.json():
                # ... many nested conditions
```

**Solution:** Extract nested logic into separate functions.

#### 3. Maximum Function Length

Target: **< 50 lines per function**

Long functions are hard to test and understand. If a function exceeds 50 lines, consider refactoring.

#### 4. Early Returns (Guard Clauses)

Use early returns to avoid deep nesting. Maximum nesting: **3 levels**.

```python
# ✅ GOOD - Early returns, flat structure
def process_reservation(reservation: dict[str, Any]) -> dict[str, Any] | None:
    """Process reservation data."""
    if not reservation.get("id"):
        logger.warning("Reservation missing ID, skipping")
        return None

    if not reservation.get("listingMapId"):
        logger.warning("Reservation missing listing, skipping", res_id=reservation["id"])
        return None

    # Main logic here (not nested)
    return normalize_reservation(reservation)

# ❌ BAD - Deep nesting
def process_reservation(reservation: dict[str, Any]) -> dict[str, Any] | None:
    """Process reservation data."""
    if reservation.get("id"):
        if reservation.get("listingMapId"):
            # Main logic deeply nested
            return normalize_reservation(reservation)
        else:
            logger.warning("Missing listing")
            return None
    else:
        logger.warning("Missing ID")
        return None
```

#### 5. No Code Duplication (DRY)

Don't copy-paste code blocks. Extract common logic into reusable functions.

```python
# ✅ GOOD - Shared logic extracted
def upsert_data(
    table: type[Base],
    rows: list[dict[str, Any]],
    conflict_column: str,
    conn: Connection,
) -> None:
    """Generic upsert logic for any table."""
    stmt = insert(table).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[conflict_column],
        set_={
            "raw_payload": stmt.excluded.raw_payload,
            "updated_at": stmt.excluded.updated_at,
        },
        where=table.raw_payload.is_distinct_from(stmt.excluded.raw_payload),
    )
    conn.execute(stmt)

# ❌ BAD - Duplicated logic in insert_listings, insert_reservations, etc.
```

### Error Handling

#### Never Use Bare `except:`

Always catch specific exceptions. Bare `except:` can hide bugs.

```python
# ✅ GOOD - Specific exception handling
try:
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()
except requests.Timeout as e:
    logger.error("API timeout", url=url, error=str(e))
    raise
except requests.HTTPError as e:
    if e.response.status_code == 404:
        logger.warning("Resource not found", url=url)
        return None
    logger.error("API error", url=url, status=e.response.status_code)
    raise
except Exception as e:
    logger.exception("Unexpected error", url=url)
    raise

# ❌ BAD - Bare except
try:
    response = requests.get(url)
    return response.json()
except:  # Catches KeyboardInterrupt, SystemExit, etc!
    return None
```

#### Log Errors with Context

Always include relevant context in error logs.

```python
# ✅ GOOD - Structured logging with context
logger.error(
    "Failed to insert listings",
    account_id=account_id,
    count=len(data),
    error=str(e),
)

# ❌ BAD - Generic error message
logger.error("Error occurred")
```

#### Re-raise When Appropriate

Don't silently swallow exceptions unless you have a good reason.

```python
# ✅ GOOD - Log and re-raise
try:
    sync_account(account_id)
except Exception as e:
    logger.exception("Sync failed", account_id=account_id)
    raise  # Let caller handle

# ❌ BAD - Silent failure
try:
    sync_account(account_id)
except Exception:
    pass  # Error hidden!
```

### Logging Best Practices

Use **structured logging** with named parameters.

```python
import logging

logger = logging.getLogger(__name__)

# ✅ GOOD - Structured logging
logger.info("Poll completed", account_id=123, records=456, duration_ms=789)
logger.warning("Token expired", account_id=123, token_age_hours=24)
logger.error("Database insert failed", table="listings", error=str(e))

# ❌ BAD - String formatting
logger.info(f"Poll completed for account {account_id} with {records} records")
```

#### Log Levels

- **DEBUG:** Detailed diagnostic info (request/response bodies, step-by-step flow)
- **INFO:** Confirmation that things are working as expected (sync started/completed)
- **WARNING:** Something unexpected but handled (missing optional field, retrying)
- **ERROR:** Error that prevented an operation (database failure, API 500)
- **CRITICAL:** System-level failure (database unreachable, config missing)

---

## Architecture Patterns (Must Follow)

### Separation of Concerns

Keep different concerns in different modules:

- **Network logic** → `sync_hostaway/network/`
- **Database logic** → `sync_hostaway/db/`
- **Business logic** → `sync_hostaway/services/`
- **API routes** → `sync_hostaway/routes/`
- **Data models** → `sync_hostaway/models/`

```python
# ✅ GOOD - Clear separation
# In sync_hostaway/network/client.py
def fetch_listings(token: str) -> list[dict[str, Any]]:
    """Fetch listings from Hostaway API."""
    return fetch_paginated("listings", token)

# In sync_hostaway/db/writers/listings.py
def insert_listings(engine: Engine, account_id: int, data: list[dict[str, Any]]) -> None:
    """Insert listings into database."""
    # ... database-only logic

# In sync_hostaway/pollers/listings.py
def poll_listings(account_id: int, engine: Engine, dry_run: bool = False) -> None:
    """Orchestrate listing sync (calls network and database)."""
    token = get_token(account_id)
    listings = fetch_listings(token)  # Network layer
    insert_listings(engine, account_id, listings, dry_run)  # Database layer

# ❌ BAD - Mixed concerns
def poll_listings(account_id: int) -> None:
    """Poll and save listings."""
    # Network logic mixed with database logic
    response = requests.get(f"{BASE_URL}/listings")
    data = response.json()
    conn.execute("INSERT INTO listings ...")  # SQL in poller!
```

### Dependency Injection

Pass dependencies as parameters, don't use globals or import directly.

```python
# ✅ GOOD - Dependencies injected
def sync_account(
    account_id: int,
    engine: Engine,  # Injected
    dry_run: bool = False,
) -> None:
    """Sync all data for an account."""
    poll_listings(account_id, engine, dry_run)
    poll_reservations(account_id, engine, dry_run)

# ❌ BAD - Global dependency
from sync_hostaway.db.engine import engine  # Global import

def sync_account(account_id: int) -> None:
    """Sync all data for an account."""
    poll_listings(account_id, engine)  # Uses global
```

**Why?** Dependency injection makes testing easier (you can inject mocks) and makes dependencies explicit.

### Pure Functions

Prefer pure functions (no side effects) for data transformations.

```python
# ✅ GOOD - Pure function
def normalize_listing(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize raw listing data to database format.

    Pure function: same input always produces same output, no side effects.
    """
    return {
        "id": raw["id"],
        "account_id": raw.get("accountId"),
        "raw_payload": raw,
    }

# ❌ BAD - Side effects in normalization
def normalize_listing(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize listing and log."""
    logger.info("Normalizing listing", listing_id=raw["id"])  # Side effect!
    return {"id": raw["id"], ...}
```

**Note:** It's fine for orchestration functions (pollers, services) to have side effects. Just keep data transformation functions pure.

### Database Patterns

#### Always Specify Schema

```python
# ✅ GOOD - Explicit schema
class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"schema": "hostaway"}
    ...

# In migrations
op.create_table("accounts", ..., schema="hostaway")

# ❌ BAD - Missing schema (uses public schema)
class Listing(Base):
    __tablename__ = "listings"
```

#### Always Use Transactions

```python
# ✅ GOOD - Explicit transaction
def insert_listings(engine: Engine, account_id: int, data: list[dict[str, Any]]) -> None:
    """Insert listings into database."""
    with engine.begin() as conn:  # Transaction
        stmt = insert(Listing).values(rows)
        conn.execute(stmt)

# ❌ BAD - No transaction
def insert_listings(engine: Engine, account_id: int, data: list[dict[str, Any]]) -> None:
    conn = engine.connect()  # No transaction!
    stmt = insert(Listing).values(rows)
    conn.execute(stmt)
    conn.close()
```

#### Prefer SQLAlchemy Core for Bulk Operations

```python
# ✅ GOOD - Use Core for bulk inserts
from sqlalchemy import insert

stmt = insert(Listing).values(rows)
stmt = stmt.on_conflict_do_update(...)
conn.execute(stmt)

# ❌ BAD - Raw SQL strings
conn.execute("INSERT INTO hostaway.listings (id, ...) VALUES (%s, ...)", rows)
```

**Pattern:** Use ORM for models and relationships, Core for bulk operations.

---

## Testing Requirements

### Coverage Standards

- **Minimum Overall Coverage:** 80%
- **Core Modules:** 90% coverage
  - `sync_hostaway/network/client.py`
  - `sync_hostaway/db/writers/*.py`
  - `sync_hostaway/pollers/*.py`

### Test Organization

Tests are organized by type using pytest markers:

```python
@pytest.mark.unit           # Fast, isolated, mocked dependencies
@pytest.mark.integration    # Real DB, mocked external APIs
@pytest.mark.functional     # Full feature workflows
@pytest.mark.e2e            # End-to-end with real external APIs (use sparingly)
```

**Directory Structure:**
```
tests/
├── unit/                   # Fast isolated tests
│   ├── network/
│   ├── normalizers/
│   └── pollers/
├── integration/            # Real DB, mocked APIs
│   ├── db/
│   ├── network/
│   └── services/
└── fixtures/               # Shared test data
```

### Running Tests

```bash
# Run all tests
make test

# Run only unit tests (fast)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run with coverage report
pytest --cov=sync_hostaway --cov-report=html

# Run specific test file
pytest tests/unit/network/test_client.py

# Run specific test
pytest tests/unit/network/test_client.py::test_fetch_page_retries_on_429 -v
```

### Writing Tests

#### Test Naming Convention

```python
def test_<function>_<scenario>_<expected_result>():
    """Test that <function> <expected_result> when <scenario>."""
    ...

# Examples:
def test_fetch_page_retries_on_rate_limit():
    """Test that fetch_page retries when API returns 429."""
    ...

def test_insert_listings_skips_unchanged_payload():
    """Test that insert_listings skips update when payload hasn't changed."""
    ...
```

#### Unit Test Example

```python
import pytest
from unittest.mock import Mock, patch
from sync_hostaway.network.client import fetch_page

@pytest.mark.unit
def test_fetch_page_retries_on_429():
    """Test that fetch_page retries when API returns 429 rate limit."""
    # Arrange
    mock_response_fail = Mock()
    mock_response_fail.status_code = 429
    mock_response_fail.json.return_value = {"error": "Rate limited"}

    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"result": [], "count": 0}

    with patch("requests.get") as mock_get:
        # First call fails with 429, second succeeds
        mock_get.side_effect = [mock_response_fail, mock_response_success]

        # Act
        result, status = fetch_page("listings", "test-token", page_number=0)

        # Assert
        assert status == 200
        assert result == {"result": [], "count": 0}
        assert mock_get.call_count == 2  # Retried once
```

#### Integration Test Example

```python
import pytest
from sqlalchemy import select
from sync_hostaway.db.writers.listings import insert_listings
from sync_hostaway.models.listings import Listing

@pytest.mark.integration
def test_insert_listings_creates_new_records(test_engine):
    """Test that insert_listings creates new records in database."""
    # Arrange
    account_id = 12345
    data = [
        {"id": 1, "name": "Test Listing 1"},
        {"id": 2, "name": "Test Listing 2"},
    ]

    # Act
    insert_listings(test_engine, account_id, data)

    # Assert
    with test_engine.connect() as conn:
        result = conn.execute(
            select(Listing).where(Listing.account_id == account_id)
        ).fetchall()

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2
```

### Test Fixtures

Use pytest fixtures for common setup:

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sync_hostaway.models.base import Base

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine("postgresql://localhost/test_db")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="function")
def clean_db(test_engine):
    """Clean database before each test."""
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
```

---

## Development Workflow

### Starting a New Feature

```bash
# 1. Create feature branch
git checkout main
git pull origin main
git checkout -b feature/add-webhook-auth

# 2. Make changes...
# Edit files in sync_hostaway/

# 3. Add tests FIRST (TDD approach)
# Create test file in tests/unit/ or tests/integration/

# 4. Run tests
make test

# 5. Check code quality
make format      # Auto-format code
make lint        # Run pre-commit checks
mypy sync_hostaway/  # Type check

# 6. Commit changes
git add .
git commit -m "feat: Add webhook Basic Auth validation"

# Pre-commit hooks run automatically!

# 7. Push and create PR
git push origin feature/add-webhook-auth
```

### Pull Request Requirements

Before creating a PR, ensure:

- [ ] All tests pass (`make test`)
- [ ] Coverage maintained or increased (`pytest --cov`)
- [ ] Type hints on all new functions
- [ ] Docstrings on all public functions
- [ ] Code formatted (`make format`)
- [ ] Pre-commit hooks pass (`make lint`)
- [ ] No type errors (`mypy sync_hostaway/`)
- [ ] Updated relevant documentation

### Commit Message Format

We follow **Conventional Commits**:

```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Adding or updating tests
- `refactor:` Code refactoring (no functional changes)
- `chore:` Maintenance tasks (dependencies, build config)
- `perf:` Performance improvements
- `style:` Code style changes (formatting, no logic changes)

**Examples:**
```
feat: Add webhook Basic Auth validation

Implements HTTP Basic Auth for /webhooks/hostaway endpoint.
Credentials are validated against accounts table.

Closes #123
```

```
fix: Correct pagination offset calculation

Changed from page parameter to offset calculation.
Hostaway API uses offset, not page numbers.

Fixes #456
```

---

## Make Commands Reference

All available commands from `Makefile`:

```bash
make help            # Show all available commands
make install         # Install production dependencies only
make install-dev     # Install dev + production dependencies
make venv            # Create virtualenv and install dev dependencies
make build           # Build Docker image
make shell           # Interactive Docker shell
make test            # Run all tests with pytest
make test-container  # Run tests inside Docker container
make lint            # Run pre-commit hooks on all files
make format          # Auto-format code (ruff + black)
make clean           # Remove Python cache files
make run-api         # Start FastAPI server on port 8000 (dev mode with reload)
```

### Common Workflows

```bash
# Start local development
docker-compose up -d
make run-api

# Run full quality check before commit
make format
make lint
make test

# Build and test in Docker
make build
make test-container
```

---

## Pre-Commit Hooks

Pre-commit hooks run automatically on `git commit`. Configured in `.pre-commit-config.yaml`.

### Installed Hooks

1. **Black** (v24.4.2) - Code formatting
2. **Ruff** (v0.4.3) - Linting and import sorting
3. **Mypy** (v1.10.0) - Static type checking
4. **End-of-file fixer** - Ensures files end with newline
5. **Trailing whitespace** - Removes trailing spaces

### Setup

```bash
# Install pre-commit (one-time)
pip install pre-commit
pre-commit install

# Run manually on all files
pre-commit run --all-files

# Run manually on staged files
pre-commit run

# Skip hooks (emergency use only!)
git commit --no-verify -m "Emergency fix"
```

### Updating Hooks

```bash
# Update to latest versions
pre-commit autoupdate

# This updates .pre-commit-config.yaml with new versions
```

---

## Troubleshooting

### Mypy Errors

**Problem:** Mypy strict mode reports missing type hints

```bash
error: Function is missing a return type annotation
```

**Solution:** Add return type annotation
```python
def fetch_data(endpoint: str) -> dict[str, Any]:  # Add return type
    ...
```

---

### Pre-commit Failures

**Problem:** Pre-commit hooks fail on commit

**Solution:** Run hooks manually and fix issues
```bash
pre-commit run --all-files
make format  # Auto-fix formatting
```

---

### Import Errors in Tests

**Problem:** `ModuleNotFoundError: No module named 'sync_hostaway'`

**Solution:** Set PYTHONPATH or install in editable mode
```bash
# Option 1: Set PYTHONPATH
export PYTHONPATH=.
pytest

# Option 2: Install in editable mode
pip install -e .
pytest
```

---

### Docker Compose Database Connection

**Problem:** App can't connect to PostgreSQL

**Solution:** Check service health
```bash
docker-compose ps  # Check if postgres is healthy
docker-compose logs postgres  # View postgres logs

# Restart services
docker-compose down
docker-compose up -d
```

---

### Alembic Migration Errors

**Problem:** `Target database is not up to date`

**Solution:** Run migrations
```bash
alembic upgrade head

# If inside Docker
docker-compose exec app alembic upgrade head
```

---

## Resources

### Official Documentation

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Mypy Documentation](https://mypy.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

### Style Guides

- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [PEP 8 – Style Guide for Python Code](https://pep8.org/)
- [PEP 484 – Type Hints](https://peps.python.org/pep-0484/)

### Project-Specific Guides

- [Technical Requirements](docs/technical-requirements.md) - Comprehensive feature requirements
- [Architecture](docs/ARCHITECTURE.md) - High-level system design
- [Implementation Status](docs/implementation-status.md) - Current state audit

---

## Questions?

If you have questions about these guidelines or need clarification on any patterns, please:

1. Check existing code for examples
2. Review the resources above
3. Open a discussion issue on GitHub
4. Ask in team chat

---

**Last Updated:** 2025-10-21
**Version:** 1.0.0
