# P2 - Medium Priority Tasks (Technical Debt & Improvements)

**Priority:** Medium - These improve maintainability and reduce technical debt

**Estimated Total Effort:** 12-16 hours

---

## 1. Refactor Long Functions in routes/accounts.py

**Status:** 3 functions exceed 50 line target
**Effort:** 3-4 hours
**Impact:** Improved readability and testability

### Functions to Refactor

| Function | Current Lines | Target Lines | Issue |
|----------|--------------|--------------|-------|
| `create_account()` | ~82 | < 50 | Verbose error handling |
| `trigger_sync()` | ~65 | < 50 | Mixed validation + logic |
| `get_account()` | ~70 | < 50 | Nested error handling |

### Refactoring Strategy

#### Extract Validation Functions
```python
# Create sync_hostaway/routes/_account_validation.py

def validate_account_payload(payload: AccountCreatePayload) -> None:
    """
    Validate account creation payload.

    Args:
        payload: Account creation data

    Raises:
        HTTPException: If validation fails
    """
    if not payload.client_secret:
        raise HTTPException(
            status_code=400,
            detail="Client secret is required"
        )

def validate_account_exists(conn: Connection, account_id: int) -> None:
    """
    Check if account already exists and raise if so.

    Args:
        conn: Database connection
        account_id: Account ID to check

    Raises:
        HTTPException: If account exists
    """
    if account_exists(conn, account_id):
        raise HTTPException(
            status_code=422,
            detail=f"Account {account_id} already exists"
        )
```

#### Extract Database Operations
```python
# Create sync_hostaway/routes/_account_operations.py

def create_account_record(
    payload: AccountCreatePayload
) -> None:
    """
    Insert new account record into database.

    Args:
        payload: Account creation data
    """
    insert_accounts(
        engine=engine,
        data=[{
            "account_id": payload.account_id,
            "client_secret": payload.client_secret,
            "customer_id": payload.customer_id,
            "access_token": None,
            "webhook_login": None,
            "webhook_password": None,
        }],
    )
```

#### Simplified Route Handler
```python
# In sync_hostaway/routes/accounts.py

from ._account_validation import (
    validate_account_payload,
    validate_account_exists,
)
from ._account_operations import create_account_record

@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreatePayload,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Create or upsert a Hostaway account."""
    try:
        validate_account_payload(payload)

        with engine.connect() as conn:
            validate_account_exists(conn, payload.account_id)

        create_account_record(payload)

        logger.info("Account %s created", payload.account_id)

        background_tasks.add_task(
            sync_account,
            account_id=payload.account_id,
            mode=SyncMode.FULL,
            dry_run=DRY_RUN,
        )

        return {"message": "Account created. Sync scheduled."}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Account creation failed")
        raise HTTPException(500, "Internal server error")
```

### Benefits
- Functions < 30 lines (well under 50 line target)
- Validation logic reusable
- Database operations testable in isolation
- Route handlers focus on HTTP concerns only

### Files to Create
- `sync_hostaway/routes/_account_validation.py` (new)
- `sync_hostaway/routes/_account_operations.py` (new)
- `tests/unit/routes/test_account_validation.py` (new)

### Files to Modify
- `sync_hostaway/routes/accounts.py` (refactor 3 functions)

### Verification
```bash
pytest tests/unit/routes/ -v
ruff check sync_hostaway/routes/
# All functions should be < 50 lines
```

### References
- Implementation Status: Line 816-846
- CONTRIBUTING.md: Function Length section

---

## 2. Add Missing Docstrings to Database Layer

**Status:** ~90% coverage, some gaps in helpers
**Effort:** 1-2 hours
**Impact:** Complete documentation

### Files Needing Docstrings

#### db/readers/accounts.py
Missing docstrings on:
- Internal helper functions
- Some query builders

#### db/writers/accounts.py
Missing docstrings on:
- `_build_account_row()` (if exists)
- Internal validation helpers

### Docstring Template
```python
def get_account_credentials(conn: Connection, account_id: int) -> dict[str, str] | None:
    """
    Fetch access_token and client_secret for given account.

    Args:
        conn: Active SQLAlchemy database connection
        account_id: Hostaway account ID

    Returns:
        Dict with 'access_token' and 'client_secret', or None if not found

    Example:
        >>> with engine.connect() as conn:
        ...     creds = get_account_credentials(conn, 12345)
        ...     if creds:
        ...         print(creds["access_token"])
    """
    ...
```

### Verification
```bash
# Check for missing docstrings
ruff check --select D sync_hostaway/db/
```

### Files to Modify
- `sync_hostaway/db/readers/accounts.py`
- `sync_hostaway/db/writers/accounts.py`

### References
- Implementation Status: Line 1252-1260
- CONTRIBUTING.md: Docstrings (Google Style)

---

## 3. Extract Duplicate Upsert Logic

**Status:** Similar upsert pattern in 3 writer files
**Effort:** 2-3 hours
**Impact:** DRY principle, easier maintenance

### Current Duplication
Pattern repeated in:
- `db/writers/listings.py`
- `db/writers/reservations.py`
- `db/writers/messages.py`

```python
# Duplicated in all 3 files
stmt = insert(Table).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=[...],
    set_={
        "raw_payload": stmt.excluded.raw_payload,
        "updated_at": stmt.excluded.updated_at,
    },
    where=Table.raw_payload.is_distinct_from(stmt.excluded.raw_payload),
)
conn.execute(stmt)
```

### Proposed Solution

#### Create Generic Upsert Helper
```python
# sync_hostaway/db/writers/_upsert.py (new file)

from typing import Any, TypeVar
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

T = TypeVar("T")

def upsert_with_distinct_check(
    conn: Connection,
    table: type[T],
    rows: list[dict[str, Any]],
    conflict_column: str,
    distinct_column: str = "raw_payload",
    update_columns: list[str] | None = None,
) -> None:
    """
    Perform upsert with IS DISTINCT FROM optimization.

    Only updates rows where the distinct_column value has actually changed,
    preventing unnecessary writes and updated_at timestamp changes.

    Args:
        conn: Active database connection
        table: SQLAlchemy ORM table class
        rows: List of row dicts to upsert
        conflict_column: Column name for ON CONFLICT (usually "id")
        distinct_column: Column to check for changes (default: "raw_payload")
        update_columns: Columns to update (default: [distinct_column, "updated_at"])

    Example:
        >>> upsert_with_distinct_check(
        ...     conn=conn,
        ...     table=Listing,
        ...     rows=[{"id": 1, "raw_payload": {...}, ...}],
        ...     conflict_column="id",
        ... )
    """
    if not rows:
        return

    if update_columns is None:
        update_columns = [distinct_column, "updated_at"]

    stmt = insert(table).values(rows)

    # Build set_ dict dynamically
    set_dict = {
        col: getattr(stmt.excluded, col)
        for col in update_columns
    }

    # Build IS DISTINCT FROM check
    distinct_check = getattr(table, distinct_column).is_distinct_from(
        getattr(stmt.excluded, distinct_column)
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=[conflict_column],
        set_=set_dict,
        where=distinct_check,
    )

    conn.execute(stmt)
```

#### Refactored Writer
```python
# sync_hostaway/db/writers/listings.py (simplified)

from ._upsert import upsert_with_distinct_check

def insert_listings(
    engine: Engine,
    account_id: int,
    data: list[dict[str, Any]],
    dry_run: bool = False
) -> None:
    """Upsert listings into database."""
    now = datetime.utcnow()
    rows = [
        {
            "id": listing["id"],
            "account_id": account_id,
            "customer_id": None,
            "raw_payload": listing,
            "created_at": now,
            "updated_at": now,
        }
        for listing in data
        if listing.get("id")
    ]

    if dry_run:
        logger.info("[DRY RUN] Would upsert %d listings", len(rows))
        return

    with engine.begin() as conn:
        upsert_with_distinct_check(
            conn=conn,
            table=Listing,
            rows=rows,
            conflict_column="id",
        )

    logger.info("Upserted %d listings", len(rows))
```

### Benefits
- Eliminates duplication across 3 files
- Centralizes upsert logic for easier maintenance
- Reusable for future entity types
- Easier to add optimizations (e.g., batch size tuning)

### Trade-offs
- Slightly more complex abstraction
- Type safety requires careful generic handling

### Decision
**Recommended:** Implement if team is comfortable with generics. Otherwise, keep current pattern (it works well).

### Files to Create
- `sync_hostaway/db/writers/_upsert.py` (new)
- `tests/unit/db/writers/test_upsert.py` (new)

### Files to Modify
- `sync_hostaway/db/writers/listings.py`
- `sync_hostaway/db/writers/reservations.py`
- `sync_hostaway/db/writers/messages.py`

### References
- Implementation Status: Line 855-895
- CONTRIBUTING.md: No Code Duplication (DRY)

---

## 4. Add CI/CD Pipeline

**Status:** No `.github/workflows/` directory
**Effort:** 2-3 hours
**Impact:** Automated testing and quality checks

### Requirements

#### 4.1 Create Basic CI Workflow
```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r dev-requirements.txt

      - name: Run linters
        run: |
          ruff check .
          black --check .

      - name: Run type checker
        run: mypy sync_hostaway/

      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/postgres
        run: |
          PYTHONPATH=. pytest --cov=sync_hostaway --cov-report=xml

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

#### 4.2 Add Status Badge to README
```markdown
# Sync Hostaway

[![CI](https://github.com/user/sync-hostaway/actions/workflows/ci.yml/badge.svg)](https://github.com/user/sync-hostaway/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/user/sync-hostaway/branch/main/graph/badge.svg)](https://codecov.io/gh/user/sync-hostaway)

...
```

### Files to Create
- `.github/workflows/ci.yml` (new)

### Files to Modify
- `README.md` (add badges)

### Verification
```bash
# Push to trigger CI
git add .github/workflows/ci.yml
git commit -m "ci: Add GitHub Actions workflow"
git push

# Check GitHub Actions tab
```

### References
- Discovery Summary: No CI/CD found
- CONTRIBUTING.md: PR Requirements

---

## 5. Improve Database Connection Management

**Status:** Singleton engine pattern, no pooling config
**Effort:** 1-2 hours
**Impact:** Better connection handling for production

### Current State
```python
# sync_hostaway/db/engine.py (minimal)
engine = create_engine(DATABASE_URL, future=True)
```

### Improvements

#### 5.1 Add Connection Pooling Configuration
```python
# sync_hostaway/db/engine.py
from sqlalchemy import create_engine
from sync_hostaway.config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set.")

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_size=10,              # Max connections in pool
    max_overflow=20,            # Additional connections when pool full
    pool_pre_ping=True,         # Verify connections before use
    pool_recycle=3600,          # Recycle connections after 1 hour
    echo=False,                 # Set True for SQL logging in dev
)
```

#### 5.2 Add Engine Health Check
```python
def check_engine_health() -> bool:
    """
    Check if database engine is healthy.

    Returns:
        bool: True if database is reachable
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
```

#### 5.3 Add to Readiness Endpoint
```python
# In routes/health.py
from sync_hostaway.db.engine import check_engine_health

@router.get("/ready")
async def ready():
    if not check_engine_health():
        raise HTTPException(503, "Database unavailable")
    return {"status": "ready"}
```

### Environment Variables (Optional)
```bash
# .env
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_RECYCLE=3600
```

### Files to Modify
- `sync_hostaway/db/engine.py`
- `sync_hostaway/config.py` (if adding env vars)
- `sync_hostaway/routes/health.py` (use health check)

### References
- Technical Requirements: Line 1796-1810
- CONTRIBUTING.md: Database Patterns

---

## Summary

| Task | Effort | Impact | Dependencies |
|------|--------|--------|--------------|
| Refactor long functions | 3-4 hrs | Maintainability | None |
| Add missing docstrings | 1-2 hrs | Documentation | None |
| Extract upsert logic | 2-3 hrs | DRY principle | None |
| Add CI/CD pipeline | 2-3 hrs | Automation | None |
| Improve DB connections | 1-2 hrs | Production ready | None |

**Total P2 Effort:** 12-16 hours

---

## Recommended Order

1. **Add CI/CD** (2-3 hrs) - Establishes quality gates early
2. **Improve DB connections** (1-2 hrs) - Production requirement
3. **Add missing docstrings** (1-2 hrs) - Quick documentation win
4. **Refactor long functions** (3-4 hrs) - Improves maintainability
5. **Extract upsert logic** (2-3 hrs) - Optional DRY improvement

---

## Next Steps

After P2 tasks:
- Review P3 tasks (optimizations, advanced features)
- Update implementation-status.md
- Consider backlog items from Technical Requirements doc
