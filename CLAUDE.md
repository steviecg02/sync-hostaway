# Claude Code Instructions for sync-hostaway

**Purpose:** This document provides context and instructions for Claude Code when working on this repository.

**Last Updated:** 2025-10-21

---

## Quick Start (Read This First!)

### 1. Understanding the Project

sync-hostaway is a **multi-tenant Hostaway API sync service** built with Python/FastAPI/PostgreSQL. It polls the Hostaway API to sync listings, reservations, and messages into a local database.

**Status:** ~70% complete, production-quality codebase with low technical debt

**Key Context:** This is part of a larger multi-PMS platform (future: sync-guesty, sync-hospitable, etc.)

---

### 2. Essential Documents (Read Before Coding)

**ALWAYS read these documents before starting ANY task:**

1. **`docs/implementation-status.md`** ← **START HERE**
   - Current state of codebase (what exists vs what's missing)
   - Known issues and bugs
   - Code quality assessment
   - Feature completion status

2. **`CONTRIBUTING.md`** ← **CODE STANDARDS**
   - Required: Type hints on all functions
   - Required: Docstrings (Google style) on public functions
   - Required: Tests before marking features complete
   - Code quality patterns (separation of concerns, dependency injection, etc.)
   - Development workflow and commit conventions

3. **`docs/ARCHITECTURE.md`** ← **SYSTEM DESIGN**
   - High-level architecture overview
   - Database schema
   - Key design patterns (IS DISTINCT FROM, explicit account_id, etc.)
   - Technology stack

4. **`docs/technical-requirements.md`** ← **COMPREHENSIVE SPEC**
   - Detailed technical requirements (2,800+ lines)
   - All features from original ChatGPT conversations
   - Implementation decisions and rationale

5. **`tasks/` directory** ← **WORK TRACKING**
   - `p0-critical.md` - Blocking issues (FIX THESE FIRST)
   - `p1-high.md` - Quality & production readiness
   - `p2-medium.md` - Technical debt
   - `p3-low.md` - Optimizations
   - `missing-features.md` - Features from tech doc not yet implemented
   - `code-quality-debt.md` - Quality issues to fix

---

## Critical Constraints & Requirements

### Type Hints (REQUIRED)

**Mypy strict mode is enabled.** All functions MUST have complete type hints.

```python
from __future__ import annotations  # Use this for clean forward references
from typing import Any

# ✅ CORRECT
def fetch_data(endpoint: str, page: int = 0) -> dict[str, Any]:
    ...

# ❌ WRONG - Missing type hints
def fetch_data(endpoint, page=0):
    ...
```

**Current Status:**
- 9 mypy errors exist (P0 to fix)
- Run `mypy sync_hostaway/` to check

---

### Docstrings (REQUIRED)

All **public** functions must have Google-style docstrings.

```python
def sync_account(account_id: int, mode: SyncMode, dry_run: bool = False) -> None:
    """
    Sync all data for a single Hostaway account.

    Fetches listings, reservations, and messages from Hostaway API and
    upserts them into the database.

    Args:
        account_id: Hostaway account ID to sync
        mode: Sync mode (FULL or DIFFERENTIAL)
        dry_run: If True, skip database writes (log only)

    Raises:
        requests.HTTPError: If API calls fail after retries
        DatabaseError: If database writes fail

    Example:
        >>> sync_account(12345, SyncMode.FULL, dry_run=False)
    """
    ...
```

---

### Tests (REQUIRED)

**DO NOT mark features complete without tests.**

**Test Organization:**
```python
# tests/unit/ - Fast, isolated, mocked dependencies
import pytest
from unittest.mock import Mock, patch

@pytest.mark.unit
def test_fetch_page_retries_on_429():
    """Test that fetch_page retries when API returns 429 rate limit."""
    ...

# tests/integration/ - Real DB, mocked external APIs
@pytest.mark.integration
def test_insert_listings_creates_new_records(test_engine):
    """Test that insert_listings creates new records in database."""
    ...
```

**Coverage Targets:**
- Overall: 80% minimum
- Core modules: 90% (client, auth, writers, services)

**Current Status:**
- ⚠️ Tests exist but cannot run (ModuleNotFoundError)
- **P0 FIX REQUIRED:** See `tasks/p0-critical.md` #1

---

## Critical Known Issues (P0)

### 🚨 MUST FIX BEFORE OTHER WORK

1. **Test Environment Broken** (`tasks/p0-critical.md` #1)
   - All tests fail with `ModuleNotFoundError: No module named 'sync_hostaway'`
   - Fix: Update Makefile with `PYTHONPATH=.`
   - **Blocks:** All testing and coverage measurement

2. **SyncMode.INCREMENTAL Doesn't Exist** (`tasks/p0-critical.md` #2)
   - `routes/accounts.py:111` references undefined enum value
   - Fix: Add `INCREMENTAL = "incremental"` to SyncMode enum
   - **Blocks:** Incremental sync mode usage (runtime error)

3. **ALLOWED_ORIGINS Type Mismatch** (`tasks/p0-critical.md` #3)
   - Type errors in `config.py` and `main.py`
   - Fix: See task file for detailed solution
   - **Blocks:** Type checking passes

4. **Webhook Implementation Incomplete** (`tasks/p0-critical.md` #4)
   - Only 25% complete (basic endpoint, no event handlers)
   - Fix: Implement event routing and handler functions
   - **Blocks:** Real-time webhook-driven sync

**Before starting ANY new work, check if these P0 issues are fixed.**

---

## Common Patterns in This Codebase

### 1. Database Operations

**ALWAYS specify schema:**
```python
class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"schema": "hostaway"}  # REQUIRED
```

**ALWAYS use transactions:**
```python
with engine.begin() as conn:  # Transaction context
    stmt = insert(Listing).values(rows)
    conn.execute(stmt)
# Auto-commit on exit
```

**Use IS DISTINCT FROM for upserts:**
```python
stmt = stmt.on_conflict_do_update(
    index_elements=["id"],
    set_={
        "raw_payload": stmt.excluded.raw_payload,
        "updated_at": stmt.excluded.updated_at,
    },
    where=Listing.raw_payload.is_distinct_from(stmt.excluded.raw_payload),
    # ↑ Only updates if payload actually changed
)
```

---

### 2. Error Handling

**NEVER use bare `except:`**
```python
# ✅ CORRECT - Specific exceptions
try:
    result = operation()
except requests.Timeout as e:
    logger.error("Operation timed out", error=str(e))
    raise
except requests.HTTPError as e:
    if e.response.status_code == 404:
        return None  # Expected case
    logger.error("HTTP error", status=e.response.status_code)
    raise

# ❌ WRONG - Bare except
try:
    result = operation()
except:  # Catches SystemExit, KeyboardInterrupt, etc!
    return None
```

**ALWAYS log errors with context:**
```python
logger.error(
    "Failed to insert listings",
    account_id=account_id,
    count=len(data),
    error=str(e),
)
```

---

### 3. Function Design

**ALWAYS pass account_id explicitly (Critical Bug Fix):**
```python
# ✅ CORRECT
def insert_listings(
    engine: Engine,
    account_id: int,  # Explicit parameter
    data: list[dict[str, Any]],
) -> None:
    for listing in data:
        rows.append({
            "id": listing["id"],
            "account_id": account_id,  # From parameter, not payload
            ...
        })

# ❌ WRONG - DO NOT DO THIS
def insert_listings(engine: Engine, data: list[dict[str, Any]]) -> None:
    for listing in data:
        account_id = listing.get("accountId")  # May be None!
```

**Why:** Hostaway API doesn't always include `accountId` in payloads. This was a critical bug.

**Reference:** `docs/technical-requirements.md` Line 1165-1189

---

### 4. Retry Logic

**Only retry transient failures:**
```python
def should_retry(res: requests.Response | None, err: Exception | None) -> bool:
    # Retry these
    if res and res.status_code == 429:  # Rate limit
        return True
    if res and 500 <= res.status_code < 600:  # Server error
        return True
    if isinstance(err, requests.Timeout):  # Network issue
        return True

    # Do NOT retry these
    if res and res.status_code in [400, 404, 422]:  # Client errors
        return False

    return False
```

---

## Development Workflow

### Starting a Task

```bash
# 1. Read implementation-status.md and relevant task file
cat docs/implementation-status.md
cat tasks/p0-critical.md  # Or p1-high.md, etc.

# 2. Check if feature already exists
grep -r "function_name" sync_hostaway/

# 3. Create feature branch
git checkout -b feature/add-webhook-handlers

# 4. Make changes following CONTRIBUTING.md standards

# 5. Run quality checks
make format      # Auto-format code
make lint        # Run pre-commit hooks
mypy sync_hostaway/  # Type check

# 6. Write tests BEFORE marking complete
pytest tests/unit/... -v

# 7. Commit with conventional commit format
git commit -m "feat: Add webhook event handlers for listings"
```

---

### Before Marking a Feature Complete

**Checklist:**
- [ ] Type hints on all new functions
- [ ] Docstrings on all public functions
- [ ] Unit tests written and passing
- [ ] Integration tests if touching database
- [ ] All quality checks pass (lint, typecheck)
- [ ] Updated `implementation-status.md` if major feature

**Run:**
```bash
make test            # All tests pass
mypy sync_hostaway/  # No type errors
make lint            # All checks pass
```

---

## When Implementing Features

### Check If It Exists First

**ALWAYS search codebase before implementing:**
```bash
# Search for function/class
grep -r "class_name\|function_name" sync_hostaway/

# Check task files
cat tasks/missing-features.md  # Is it listed as missing?
cat docs/implementation-status.md  # What's the current status?
```

**Common Gotcha:** Some features are partially implemented. Check implementation-status.md for current state.

---

### Follow Architecture Patterns

**Separation of Concerns:**
- Network logic → `sync_hostaway/network/`
- Database logic → `sync_hostaway/db/`
- Business logic → `sync_hostaway/services/`, `sync_hostaway/pollers/`
- API routes → `sync_hostaway/routes/`
- Data models → `sync_hostaway/models/`

**Example:**
```python
# ✅ CORRECT - Separation of concerns
# In sync_hostaway/network/client.py
def fetch_listings(account_id: int) -> list[dict[str, Any]]:
    """Fetch listings from Hostaway API."""
    return fetch_paginated("listings", account_id)

# In sync_hostaway/db/writers/listings.py
def insert_listings(engine: Engine, account_id: int, data: list[dict[str, Any]]) -> None:
    """Insert listings into database."""
    # ... database-only logic

# In sync_hostaway/pollers/listings.py
def poll_listings(account_id: int) -> list[dict[str, Any]]:
    """Orchestrate listing sync (network + database)."""
    listings = fetch_listings(account_id)  # Network layer
    return listings

# ❌ WRONG - Mixed concerns
def poll_listings(account_id: int) -> None:
    # Network logic
    response = requests.get(f"{BASE_URL}/listings")
    data = response.json()
    # Database logic
    conn.execute("INSERT INTO listings ...")  # SQL in poller!
```

---

### Dependency Injection

**Pass dependencies as parameters:**
```python
# ✅ CORRECT - Dependency injected
def sync_account(
    account_id: int,
    engine: Engine,  # Injected
    dry_run: bool = False,
) -> None:
    poll_listings(account_id, engine, dry_run)

# ❌ AVOID - Global dependency
from sync_hostaway.db.engine import engine  # Global import

def sync_account(account_id: int) -> None:
    poll_listings(account_id, engine)  # Uses global
```

**Note:** Current codebase uses global `engine` import. This is acceptable for now but could be improved. See `tasks/p3-low.md` #3 for FastAPI dependency injection pattern.

---

## Testing Patterns

### Unit Tests (Fast, Isolated)

```python
import pytest
from unittest.mock import Mock, patch
from sync_hostaway.network.client import fetch_page

@pytest.mark.unit
def test_fetch_page_retries_on_429():
    """Test that fetch_page retries when API returns 429."""
    mock_response_fail = Mock(status_code=429)
    mock_response_success = Mock(status_code=200)
    mock_response_success.json.return_value = {"result": [], "count": 0}

    with patch("requests.get") as mock_get:
        mock_get.side_effect = [mock_response_fail, mock_response_success]

        result, status = fetch_page("listings", "test-token", page_number=0)

        assert status == 200
        assert mock_get.call_count == 2  # Retried once
```

### Integration Tests (Real DB)

```python
import pytest
from sqlalchemy import select
from sync_hostaway.db.writers.listings import insert_listings
from sync_hostaway.models.listings import Listing

@pytest.mark.integration
def test_insert_listings_creates_new_records(test_engine):
    """Test that insert_listings creates new records in database."""
    account_id = 12345
    data = [
        {"id": 1, "name": "Test Listing 1"},
        {"id": 2, "name": "Test Listing 2"},
    ]

    insert_listings(test_engine, account_id, data)

    with test_engine.connect() as conn:
        result = conn.execute(
            select(Listing).where(Listing.account_id == account_id)
        ).fetchall()

        assert len(result) == 2
```

---

## Common Tasks

### Adding a New Route

1. Check `docs/implementation-status.md` - Does it exist?
2. Follow patterns in existing routes (`routes/accounts.py`)
3. Create Pydantic schemas if needed (`schemas/`)
4. Add route to main.py
5. Write unit tests (`tests/unit/routes/`)
6. Write integration tests (`tests/integration/routes/`)

### Adding a New Database Writer

1. Follow pattern in `db/writers/listings.py`
2. Use IS DISTINCT FROM optimization
3. Pass `account_id` explicitly (not from payload)
4. Use transactions (`with engine.begin()`)
5. Write integration tests (`tests/integration/db/writers/`)

### Fixing a Bug

1. Check `docs/implementation-status.md` - Is it listed?
2. Write failing test first (TDD approach)
3. Fix bug
4. Verify test passes
5. Update implementation-status.md if bug was documented

---

## Repository Structure

```
sync-hostaway/
├── sync_hostaway/
│   ├── config.py           # Environment configuration
│   ├── logging_config.py   # Logging setup
│   ├── main.py             # FastAPI app entry point
│   ├── db/
│   │   ├── engine.py       # SQLAlchemy engine singleton
│   │   ├── readers/        # Database query functions
│   │   │   └── accounts.py
│   │   └── writers/        # Database write functions
│   │       ├── accounts.py
│   │       ├── listings.py
│   │       ├── messages.py
│   │       └── reservations.py
│   ├── models/             # SQLAlchemy ORM models
│   │   ├── base.py
│   │   ├── accounts.py
│   │   ├── listings.py
│   │   ├── messages.py
│   │   └── reservations.py
│   ├── network/            # HTTP client layer
│   │   ├── auth.py         # Token management
│   │   └── client.py       # Pagination & retry logic
│   ├── normalizers/        # Data transformation
│   │   └── messages.py
│   ├── pollers/            # Orchestration
│   │   ├── listings.py
│   │   ├── messages.py
│   │   ├── reservations.py
│   │   └── sync.py         # Legacy
│   ├── routes/             # FastAPI routes
│   │   ├── accounts.py     # Account management
│   │   ├── webhook.py      # Webhook receiver
│   │   └── main.py
│   ├── schemas/            # Pydantic models
│   │   └── accounts.py
│   └── services/           # Business logic
│       └── sync.py         # Sync orchestration
├── tests/
│   ├── unit/               # Fast, isolated tests
│   │   ├── api/
│   │   ├── network/
│   │   ├── normalizers/
│   │   └── pollers/
│   └── integration/        # Real DB tests
│       ├── db/
│       ├── network/
│       ├── pollers/
│       └── services/
├── alembic/                # Database migrations
│   └── versions/
├── docs/                   # Documentation
│   ├── implementation-status.md
│   ├── ARCHITECTURE.md
│   └── technical-requirements.md
├── tasks/                  # Work tracking
│   ├── p0-critical.md
│   ├── p1-high.md
│   ├── p2-medium.md
│   ├── p3-low.md
│   ├── missing-features.md
│   ├── code-quality-debt.md
│   └── repo-setup.md
├── CONTRIBUTING.md         # Code standards
├── CLAUDE.md               # This file
├── README.md
├── Makefile                # Development commands
├── docker-compose.yml      # Local development
├── pyproject.toml          # Tool configs
├── requirements.txt
└── dev-requirements.txt
```

---

## Make Commands

```bash
make help            # Show all commands
make install-dev     # Install dev dependencies
make test            # Run all tests
make lint            # Run pre-commit hooks
make format          # Auto-format code
make run-api         # Start FastAPI server
make build           # Build Docker image
make clean           # Remove cache files
```

---

## Important Notes

### This Codebase Was Built with ChatGPT

**Context:** The original codebase was built through ChatGPT conversations, then audited and improved by Claude Code.

**What This Means:**
- Some technical debt exists (documented in `tasks/code-quality-debt.md`)
- Architecture is sound but some implementation details need refinement
- Comprehensive documentation was created to capture ChatGPT's intent

**Your Role:** Continue improving code quality while preserving the working architecture.

---

### Multi-PMS Context

**Remember:** This is `sync-hostaway`, not `hostaway-sync`.

**Why:** This service is part of a larger multi-PMS platform:
- Each PMS gets its own sync service (sync-hostaway, sync-guesty, etc.)
- Each service stores raw data in its own schema (`hostaway`, `guesty`)
- Future normalization service will provide unified multi-PMS API

**Implication:** Don't normalize data at sync time. Store raw payloads AS-IS.

**Reference:** `docs/ARCHITECTURE.md` Multi-PMS Design Philosophy

---

## When in Doubt

1. **Read `docs/implementation-status.md`** - Current state of everything
2. **Check `CONTRIBUTING.md`** - Code standards and patterns
3. **Search existing code** - Follow established patterns
4. **Ask user** - If unclear, use AskUserQuestion tool
5. **Write tests** - Test-driven development catches issues early

---

## Final Checklist Before Completing Work

- [ ] Read relevant documentation (implementation-status.md, CONTRIBUTING.md)
- [ ] Feature doesn't already exist (checked with grep/search)
- [ ] Type hints on all new functions
- [ ] Docstrings on all public functions
- [ ] Tests written and passing
- [ ] `make lint` passes
- [ ] `mypy sync_hostaway/` passes
- [ ] Updated implementation-status.md if major change
- [ ] Followed architecture patterns (separation of concerns)
- [ ] Used established coding patterns (IS DISTINCT FROM, explicit account_id, etc.)

---

**Good luck! This is a well-structured codebase with solid foundations. Focus on quality over speed.**

**Last Updated:** 2025-10-21
**Maintained By:** Stephen Guilfoil
