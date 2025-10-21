# P0 - Critical Tasks (Blocking Development)

**Priority:** Highest - These issues block development or cause runtime errors

**Estimated Total Effort:** 9-11 hours

---

## 1. Fix Test Environment (BLOCKER)

**Status:** 🚨 Critical - Cannot run any tests
**Effort:** 15 minutes
**Impact:** Unblocks entire test suite

### Problem
All 14 test files fail with:
```
ModuleNotFoundError: No module named 'sync_hostaway'
```

### Root Cause
Package not installed, PYTHONPATH not set in test environment

### Solution Options

**Option 1: Update Makefile (Recommended)**
```makefile
# In Makefile
test:
	PYTHONPATH=. pytest -v --tb=short --cov=sync_hostaway --cov-report=html
```

**Option 2: Add setup.py**
```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="sync-hostaway",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        # Copy from requirements.txt
    ],
)
```

Then: `pip install -e .`

### Verification
```bash
make test
# Should collect and run 14 test files
```

### Files to Modify
- `Makefile` (Option 1)
- OR create `setup.py` (Option 2)

### References
- Implementation Status: Line 1040-1067
- Contributing.md: Testing section

---

## 2. Fix SyncMode.INCREMENTAL Reference Error

**Status:** 🚨 Runtime Error
**Effort:** 5 minutes
**Impact:** Prevents incremental sync mode usage

### Problem
`routes/accounts.py:111` references undefined `SyncMode.INCREMENTAL`:
```python
mode = SyncMode.FULL if mode.lower() == "full" else SyncMode.INCREMENTAL  # ❌
```

But `services/sync.py` only defines:
```python
class SyncMode(str, Enum):
    FULL = "full"
    DIFFERENTIAL = "differential"  # Not INCREMENTAL!
```

### Solution Option 1: Add INCREMENTAL (Recommended)
```python
# In sync_hostaway/services/sync.py
class SyncMode(str, Enum):
    FULL = "full"
    DIFFERENTIAL = "differential"
    INCREMENTAL = "incremental"  # Add this
```

### Solution Option 2: Use DIFFERENTIAL
```python
# In sync_hostaway/routes/accounts.py:111
mode = SyncMode.FULL if mode.lower() == "full" else SyncMode.DIFFERENTIAL
```

### Verification
```bash
mypy sync_hostaway/routes/accounts.py
# Should pass without SyncMode.INCREMENTAL error
```

### Files to Modify
- `sync_hostaway/services/sync.py` (Option 1)
- OR `sync_hostaway/routes/accounts.py` (Option 2)

### References
- Implementation Status: Line 576-600
- Mypy error output: Line 111

---

## 3. Fix ALLOWED_ORIGINS Type Issues

**Status:** 🚨 Type Safety Violation
**Effort:** 15 minutes
**Impact:** Type checking failures in config and main

### Problem 1: config.py Type Mismatch
```python
# Current (WRONG)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")  # Type: str | None
if ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS.split(",")]  # ❌ Assign list to str | None
```

### Problem 2: main.py Comparison Error
```python
# Current (WRONG)
allow_origins=["*"] if ALLOWED_ORIGINS == ["*"] else ALLOWED_ORIGINS
# Compares str | None with list[str]
```

### Solution

**In `sync_hostaway/config.py`:**
```python
# Replace lines 18-22 with:
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS")
if not ALLOWED_ORIGINS_RAW:
    raise ValueError("ALLOWED_ORIGINS must be set in the environment")

ALLOWED_ORIGINS: list[str] = [
    origin.strip() for origin in ALLOWED_ORIGINS_RAW.split(",")
]
```

**In `sync_hostaway/main.py`:**
```python
# Replace line 26 with:
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if "*" not in ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Verification
```bash
mypy sync_hostaway/config.py sync_hostaway/main.py
# Should pass with no errors
```

### Files to Modify
- `sync_hostaway/config.py` (lines 18-22)
- `sync_hostaway/main.py` (line 26)

### References
- Implementation Status: Line 602-641
- Mypy errors: config.py:20, main.py:26

---

## 4. Complete Webhook Implementation

**Status:** 🚨 25% Complete - Real-time sync non-functional
**Effort:** 6-8 hours
**Impact:** Enables real-time webhook-driven sync

### Current State
Basic endpoint exists but no event handling:
```python
# sync_hostaway/routes/webhook.py (current)
@router.post("/hostaway")
async def receive_hostaway_webhook(request: Request) -> JSONResponse:
    payload = await request.json()
    event_type = payload.get("eventType")
    logger.info("Received webhook: %s", event_type)
    # 🧪 TODO: Dispatch to sync handler  ← NEEDS IMPLEMENTATION
    return JSONResponse(content={"status": "accepted"})
```

### Requirements

#### 4.1 Add Basic Auth Validation
```python
from fastapi import Depends, HTTPException, Header
from typing import Annotated

def validate_webhook_auth(
    authorization: Annotated[str | None, Header()] = None
) -> bool:
    """Validate HTTP Basic Auth against accounts table."""
    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(401, "Unauthorized")

    # Decode Basic Auth
    # Query accounts table for matching webhook_login/webhook_password
    # Return True if valid
```

#### 4.2 Implement Event Router
```python
def route_event(event_type: str, payload: dict[str, Any]) -> None:
    """Route webhook events to appropriate handlers."""
    handlers = {
        "listing.created": handle_listing_created,
        "listing.updated": handle_listing_updated,
        "listing.deleted": handle_listing_deleted,
        "reservation.created": handle_reservation_created,
        "reservation.updated": handle_reservation_updated,
        "reservation.cancelled": handle_reservation_cancelled,
        "message.created": handle_message_created,
    }

    handler = handlers.get(event_type)
    if handler:
        handler(payload)
    else:
        logger.warning("Unknown event type: %s", event_type)
```

#### 4.3 Implement Event Handlers
```python
def handle_listing_created(payload: dict[str, Any]) -> None:
    """Handle listing.created webhook event."""
    account_id = payload.get("accountId")
    listing_data = payload.get("data", {})

    insert_listings(
        engine=engine,
        account_id=account_id,
        data=[listing_data],
        dry_run=False,
    )

# Repeat for other event types...
```

#### 4.4 Add Deduplication
- Track processed webhook IDs in database
- Skip if already processed
- Prevent duplicate writes

#### 4.5 Write Tests
```python
# tests/unit/api/test_webhook.py
@pytest.mark.unit
def test_webhook_authenticates_basic_auth():
    """Test webhook validates Basic Auth credentials."""
    ...

@pytest.mark.unit
def test_webhook_routes_listing_created():
    """Test webhook routes listing.created to correct handler."""
    ...
```

### Files to Create/Modify
- `sync_hostaway/routes/webhook.py` (major rewrite)
- `sync_hostaway/db/writers/webhooks.py` (new - for deduplication)
- `tests/unit/api/test_webhook.py` (expand)
- `tests/integration/api/test_webhook_e2e.py` (new)

### Verification
```bash
# Unit tests
pytest tests/unit/api/test_webhook.py -v

# Integration test with mock payload
curl -X POST http://localhost:8000/hostaway/webhooks/hostaway \
  -H "Authorization: Basic <encoded>" \
  -H "Content-Type: application/json" \
  -d '{"eventType": "listing.created", "accountId": 12345, "data": {...}}'
```

### References
- Implementation Status: Line 410-442
- Technical Requirements: Line 1472-1553

---

## Summary

| Task | Effort | Status | Blocker? |
|------|--------|--------|----------|
| Fix test environment | 15 min | 🚨 | YES - blocks all testing |
| Fix SyncMode.INCREMENTAL | 5 min | 🚨 | YES - runtime error |
| Fix ALLOWED_ORIGINS types | 15 min | 🚨 | YES - type safety |
| Complete webhooks | 6-8 hrs | 🚨 | YES - real-time sync |

**Total P0 Effort:** 9-11 hours

---

## Next Steps

1. **Immediately:** Fix test environment (15 min)
2. **Immediately:** Fix SyncMode.INCREMENTAL (5 min)
3. **Immediately:** Fix ALLOWED_ORIGINS (15 min)
4. **This Week:** Complete webhook implementation (6-8 hrs)

After P0 complete: Run full test suite and measure coverage → Move to P1 tasks
