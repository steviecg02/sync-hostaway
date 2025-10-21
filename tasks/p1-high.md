# P1 - High Priority Tasks (Quality & Production Readiness)

**Priority:** High - These improve code quality and prepare for production

**Estimated Total Effort:** 10-14 hours

---

## 1. Fix Remaining Mypy Type Errors

**Status:** 7 errors remaining (after P0 fixes)
**Effort:** 1-2 hours
**Impact:** Full strict mode compliance

### Errors to Fix

#### 1.1 Missing dict Type Parameters (4 errors)
**Location:** `sync_hostaway/routes/accounts.py`

**Lines:** 26, 90, 140, 206

**Problem:**
```python
def create_account(...) -> dict:  # ❌ Missing type parameters
    ...
```

**Solution:**
```python
from typing import Any

def create_account(...) -> dict[str, Any]:  # ✅ Explicit types
    ...
```

**Files:**
- `sync_hostaway/routes/accounts.py` (4 occurrences)

---

#### 1.2 sorted() Key Type Incompatibility
**Location:** `sync_hostaway/normalizers/messages.py:67`

**Problem:**
```python
sorted_messages = sorted(messages, key=lambda m: m["sent_at"])  # ❌ Key might be None
```

**Solution:**
```python
sorted_messages = sorted(
    messages,
    key=lambda m: m.get("sent_at", "")  # ✅ Handle None with default
)
```

**Files:**
- `sync_hostaway/normalizers/messages.py` (line 67)

---

### Verification
```bash
mypy sync_hostaway/
# Should show: Success: no issues found
```

### References
- Implementation Status: Line 696-738
- CONTRIBUTING.md: Type Hints section

---

## 2. Add Health & Readiness Endpoints

**Status:** Not implemented
**Effort:** 1 hour
**Impact:** Production deployment readiness

### Requirements

#### 2.1 Health Check Endpoint
**Purpose:** Kubernetes liveness probe

```python
# sync_hostaway/routes/health.py (new file)
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health() -> dict[str, str]:
    """
    Basic liveness check for container orchestration.

    Returns:
        dict: Status and version information
    """
    return {
        "status": "ok",
        "service": "sync-hostaway",
        "version": "1.0.0",
    }
```

#### 2.2 Readiness Check Endpoint
**Purpose:** Kubernetes readiness probe (checks dependencies)

```python
@router.get("/ready")
async def ready() -> dict[str, str]:
    """
    Readiness check - validates database connectivity.

    Returns:
        dict: Ready status

    Raises:
        HTTPException: 503 if database unavailable
    """
    from sync_hostaway.db.engine import engine
    from sqlalchemy import text
    from fastapi import HTTPException

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database unavailable: {str(e)}"
        )
```

#### 2.3 Register Routes
```python
# sync_hostaway/main.py
from sync_hostaway.routes.health import router as health_router

app.include_router(health_router, tags=["Health"])
```

### Testing
```bash
# Health check
curl http://localhost:8000/health
# → {"status": "ok", "service": "sync-hostaway", "version": "1.0.0"}

# Readiness check (DB running)
curl http://localhost:8000/ready
# → {"status": "ready"}

# Readiness check (DB down)
docker-compose stop postgres
curl http://localhost:8000/ready
# → 503 Service Unavailable
```

### Files to Create
- `sync_hostaway/routes/health.py` (new)
- `tests/integration/api/test_health.py` (new)

### Files to Modify
- `sync_hostaway/main.py` (add router registration)

### References
- Implementation Status: Line 904-932
- Technical Requirements: Line 1828-1851

---

## 3. Run Full Test Coverage Analysis

**Status:** Blocked by P0 (test environment fix)
**Effort:** 4-6 hours (writing missing tests)
**Impact:** Verify 80%+ coverage target

### Prerequisites
- ✅ P0 Task #1 complete (fix test environment)

### Steps

#### 3.1 Generate Coverage Report
```bash
pytest --cov=sync_hostaway --cov-report=html --cov-report=term-missing
```

#### 3.2 Review Coverage by Module
**Target Coverage:**
- Overall: 80% minimum
- Core modules: 90% minimum
  - `network/client.py`
  - `network/auth.py`
  - `db/writers/*.py`
  - `services/sync.py`

#### 3.3 Write Missing Tests
**Likely Gaps Based on Audit:**

**Routes Layer (Low Coverage Expected):**
- `tests/unit/routes/test_accounts.py` (missing)
- `tests/integration/routes/test_accounts_e2e.py` (missing)

**Database Readers (Likely Gaps):**
- `tests/unit/db/readers/test_accounts.py` (missing)

**Services Layer:**
- `tests/unit/services/test_sync.py` (missing)

**Normalizers:**
- Expand `tests/unit/normalizers/test_normalize_messages.py`

#### 3.4 Add Edge Case Tests
**Examples:**
- Empty result sets
- Invalid payloads
- Network timeouts
- Database connection failures
- Token refresh failures

### Success Criteria
```bash
pytest --cov=sync_hostaway --cov-report=term
# ---------- coverage: platform darwin, python 3.11.x -----------
# Name                              Stmts   Miss  Cover
# -----------------------------------------------------
# sync_hostaway/__init__.py             0      0   100%
# sync_hostaway/config.py              23      1    96%
# sync_hostaway/network/client.py     157     10    94%
# sync_hostaway/network/auth.py       121      8    93%
# sync_hostaway/db/writers/*.py       300     25    92%
# ...
# TOTAL                              1669    150    91%  ✅
```

### Files to Create
- Multiple new test files (see 3.3 above)

### References
- Implementation Status: Line 1040-1090
- CONTRIBUTING.md: Testing Requirements

---

## 4. Add Pre-Commit Hook Auto-Installation

**Status:** Pre-commit config exists but not auto-installed
**Effort:** 30 minutes
**Impact:** Enforces code quality on every commit

### Current State
- `.pre-commit-config.yaml` exists ✅
- Developers must manually run `pre-commit install`

### Solution

#### 4.1 Update Makefile
```makefile
install-dev:
	pip install -r requirements.txt -r dev-requirements.txt
	pre-commit install  # Add this line

venv:
	python3 -m venv venv && source venv/bin/activate && make install-dev
```

#### 4.2 Add Pre-Commit Validation to CI
**When CI exists:**
```yaml
# .github/workflows/ci.yml
- name: Run pre-commit
  run: pre-commit run --all-files
```

#### 4.3 Document in README
```markdown
## Development Setup

make venv
source venv/bin/activate
# Pre-commit hooks are now installed automatically!
```

### Verification
```bash
make venv
# Should see: "pre-commit installed at .git/hooks/pre-commit"

# Test hooks
git add .
git commit -m "test commit"
# Should run black, ruff, mypy automatically
```

### Files to Modify
- `Makefile` (install-dev target)
- `README.md` (update setup instructions)

### References
- Discovery Summary: Pre-commit hooks section
- CONTRIBUTING.md: Pre-Commit Hooks

---

## 5. Add Structured Logging

**Status:** Basic logging exists, not structured
**Effort:** 2-3 hours
**Impact:** Better log aggregation and querying

### Current State
```python
# Current (unstructured)
logger.info(f"Poll completed for account {account_id} with {records} records")
```

### Desired State
```python
# Structured
logger.info(
    "poll_completed",
    account_id=account_id,
    records=records,
    duration_ms=duration,
)
```

### Implementation

#### 5.1 Add structlog Dependency
```bash
# In requirements.txt
structlog==23.1.0
```

#### 5.2 Update logging_config.py
```python
import structlog
from sync_hostaway.config import LOG_LEVEL

def setup_logging() -> None:
    """Configure structured logging globally."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if LOG_LEVEL == "INFO" else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(LOG_LEVEL)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

#### 5.3 Update Module Logging
```python
# In each module
import structlog
logger = structlog.get_logger(__name__)

# Usage
logger.info(
    "poll_completed",
    account_id=123,
    listings_count=45,
    reservations_count=12,
    duration_ms=1234,
)
# Output: {"event": "poll_completed", "account_id": 123, ...}
```

### Migration Strategy
1. Update `logging_config.py` first
2. Migrate high-traffic modules (pollers, services)
3. Gradually update remaining modules

### Files to Modify
- `requirements.txt` (add structlog)
- `sync_hostaway/logging_config.py` (replace setup)
- All modules with logging (gradual)

### References
- Technical Requirements: Line 2610-2631
- CONTRIBUTING.md: Logging Best Practices

---

## Summary

| Task | Effort | Impact | Blocked By |
|------|--------|--------|------------|
| Fix mypy errors | 1-2 hrs | Type safety | None |
| Add health endpoints | 1 hr | Production ready | None |
| Run coverage analysis | 4-6 hrs | Quality assurance | P0 #1 |
| Auto-install pre-commit | 30 min | Code quality | None |
| Add structured logging | 2-3 hrs | Observability | None |

**Total P1 Effort:** 10-14 hours

---

## Recommended Order

1. **Fix mypy errors** (1-2 hrs) - Quick win, unblocks strict mode
2. **Add health endpoints** (1 hr) - Quick, enables production deployment
3. **Auto-install pre-commit** (30 min) - Quick, improves DX
4. **Wait for P0 #1** → **Run coverage** (4-6 hrs) - Comprehensive quality check
5. **Add structured logging** (2-3 hrs) - Can be done in parallel

---

## Next Steps After P1

After completing P1 tasks:
- Review P2 tasks (refactoring, documentation)
- Consider P3 tasks if time permits
- Update implementation-status.md with new coverage data
