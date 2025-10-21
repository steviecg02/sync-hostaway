# Code Quality Technical Debt

**Source:** Automated checks (mypy, ruff) + manual code review

**Last Updated:** 2025-10-21

---

## Critical Quality Issues (P0)

### 1. Mypy Type Errors (Strict Mode)
**Count:** 9 errors
**Impact:** Type safety violations

#### Errors Breakdown

**P0 Issues (Block Development):**
1. `config.py:20` - ALLOWED_ORIGINS type mismatch
2. `main.py:26` - ALLOWED_ORIGINS comparison error
3. `routes/accounts.py:111` - SyncMode.INCREMENTAL doesn't exist

**P1 Issues (Quality):**
4. `routes/accounts.py:26` - Missing dict type parameters
5. `routes/accounts.py:90` - Missing dict type parameters
6. `routes/accounts.py:140` - Missing dict type parameters
7. `routes/accounts.py:206` - Missing dict type parameters
8. `normalizers/messages.py:67` - sorted() key type incompatibility (2 errors)

**Fix Effort:** 1-2 hours total

**See:** `tasks/p0-critical.md` #2 and #3, `tasks/p1-high.md` #1

---

### 2. Test Environment Broken
**Issue:** All 14 test files fail with `ModuleNotFoundError`
**Impact:** Cannot run any tests (0% verified coverage)

**Root Cause:** PYTHONPATH not set, package not installed

**Fix:** Update Makefile:
```makefile
test:
	PYTHONPATH=. pytest -v --tb=short --cov=sync_hostaway
```

**Effort:** 15 minutes

**See:** `tasks/p0-critical.md` #1

---

## High Priority Quality Issues (P1)

### 1. Missing Test Coverage Data
**Status:** Tests exist but coverage unknown
**Impact:** Cannot verify 80% coverage target

**Blocked By:** P0 #2 (fix test environment)

**Action Items:**
1. Fix test environment
2. Run: `pytest --cov=sync_hostaway --cov-report=html`
3. Identify coverage gaps
4. Write missing tests to reach 80%+

**Estimated Effort:** 4-6 hours (writing missing tests)

**See:** `tasks/p1-high.md` #3

---

### 2. Long Functions in routes/accounts.py
**Count:** 3 functions exceed 50-line target
**Impact:** Reduced maintainability

**Functions:**
- `create_account()` - 82 lines
- `trigger_sync()` - 65 lines
- `get_account()` - 70 lines

**Cause:** Verbose FastAPI error handling patterns

**Solution:** Extract validation and database operations into helper functions

**Effort:** 3-4 hours

**See:** `tasks/p2-medium.md` #1

---

## Medium Priority Quality Issues (P2)

### 1. Missing Docstrings
**Count:** ~10% of functions missing docstrings
**Location:** Database layer (`db/readers/`, `db/writers/`)

**Examples:**
- Internal helper functions
- Query builders

**Impact:** Incomplete documentation

**Effort:** 1-2 hours

**See:** `tasks/p2-medium.md` #2

---

### 2. Code Duplication in Database Writers
**Pattern:** Upsert logic repeated in 3 files
**Location:**
- `db/writers/listings.py`
- `db/writers/reservations.py`
- `db/writers/messages.py`

**Duplication:**
```python
# Same pattern in all 3 files
stmt = insert(Table).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=[...],
    set_={...},
    where=Table.raw_payload.is_distinct_from(stmt.excluded.raw_payload),
)
```

**Solution:** Extract to generic `upsert_with_distinct_check()` helper

**Trade-off:** Adds abstraction complexity

**Priority:** P2-P3 (current pattern works fine, optimization)

**Effort:** 2-3 hours

**See:** `tasks/p2-medium.md` #3

---

## Low Priority Quality Issues (P3)

### 1. Raw SQL in services/sync.py
**Location:** `services/sync.py:72-80`
**Issue:** Uses `text()` for raw SQL query

```python
# Current
result = conn.execute(
    text("""
        SELECT account_id FROM hostaway.accounts
        WHERE is_active = TRUE
        ORDER BY account_id
    """)
)
```

**Better:** Use SQLAlchemy Core select()
```python
from sqlalchemy import select
from sync_hostaway.models.accounts import Account

stmt = select(Account.account_id).where(Account.is_active == True).order_by(Account.account_id)
result = conn.execute(stmt)
```

**Effort:** 15 minutes

**Impact:** Minor - consistency with rest of codebase

---

### 2. Global Engine Import Pattern
**Location:** Throughout codebase
**Issue:** `from sync_hostaway.db.engine import engine` (global import)

**Better:** FastAPI dependency injection

**Current:**
```python
from sync_hostaway.db.engine import engine

def create_account(...):
    with engine.connect() as conn:
        ...
```

**Better:**
```python
from fastapi import Depends
from sqlalchemy import Engine
from sync_hostaway.dependencies import get_db_engine

def create_account(
    ...,
    engine: Engine = Depends(get_db_engine),
):
    with engine.connect() as conn:
        ...
```

**Benefits:** Easier testing with mock engines

**Trade-off:** More verbose signatures

**Effort:** 3-4 hours (migrate all routes)

**See:** `tasks/p3-low.md` #3

---

## Quality Metrics Summary

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Mypy Errors | 9 | 0 | ❌ |
| Test Coverage | Unknown | 80% | ⚠️ Cannot measure |
| Function Complexity | All pass | < 10 | ✅ |
| Function Length | 3 violations | < 50 lines | ⚠️ |
| Docstring Coverage | 95% | 100% | ✅ Good |
| Code Formatting | 100% | 100% | ✅ Perfect |

---

## Quality Gates for CI/CD

**When CI is implemented, enforce:**

```yaml
# .github/workflows/ci.yml (future)
- name: Type check
  run: mypy sync_hostaway/
  # Must pass with 0 errors

- name: Lint
  run: ruff check .
  # Must pass

- name: Format check
  run: black --check .
  # Must pass

- name: Test coverage
  run: pytest --cov=sync_hostaway --cov-fail-under=80
  # Must reach 80% coverage
```

---

## Recommended Fix Order

### Week 1 (P0)
1. Fix test environment (15 min)
2. Fix SyncMode.INCREMENTAL (5 min)
3. Fix ALLOWED_ORIGINS types (15 min)

### Week 2 (P1)
1. Fix remaining mypy errors (1-2 hrs)
2. Run coverage, write missing tests (4-6 hrs)

### Week 3 (P2)
1. Refactor long functions (3-4 hrs)
2. Add missing docstrings (1-2 hrs)

### Optional (P3)
1. Extract duplicate upsert logic (2-3 hrs)
2. Convert raw SQL to SQLAlchemy Core (15 min)
3. Implement dependency injection (3-4 hrs)

---

## Tracking Progress

**Update this document after:**
- Fixing mypy errors (update counts)
- Running coverage (add actual percentages)
- Refactoring functions (update violation counts)
- Adding docstrings (update coverage %)

**Compare against:**
- CONTRIBUTING.md standards
- Implementation Status report

---

## Cross-Reference

- **P0 Fixes:** See `tasks/p0-critical.md`
- **P1 Fixes:** See `tasks/p1-high.md`
- **P2 Fixes:** See `tasks/p2-medium.md`
- **P3 Optimizations:** See `tasks/p3-low.md`
- **Full Audit:** See `docs/implementation-status.md`
