# P3 - Low Priority Tasks (Optimizations & Nice-to-Have)

**Priority:** Low - These are optimizations and enhancements for future consideration

**Estimated Total Effort:** 18-24 hours

---

## 1. Implement Token Cache Service

**Status:** Not implemented (uses database queries)
**Effort:** 6-8 hours
**Impact:** Performance optimization (reduces DB queries)

### Current State
Every API request fetches token from database:
```python
# network/auth.py
def get_access_token(account_id: int) -> str:
    with engine.connect() as conn:  # DB query every time
        creds = get_account_credentials(conn, account_id)
    ...
```

### Proposed Solution

#### Option 1: In-Memory Cache (Simple)
```python
# sync_hostaway/cache.py (new file)
from functools import lru_cache
from datetime import datetime, timedelta

class TokenCache:
    """In-memory token cache with TTL."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: dict[int, tuple[str, datetime]] = {}

    def get(self, account_id: int) -> str | None:
        """Get cached token if not expired."""
        if account_id in self._cache:
            token, expires_at = self._cache[account_id]
            if datetime.utcnow() < expires_at:
                return token
            # Expired, remove
            del self._cache[account_id]
        return None

    def set(self, account_id: int, token: str) -> None:
        """Cache token with TTL."""
        expires_at = datetime.utcnow() + self.ttl
        self._cache[account_id] = (token, expires_at)

    def invalidate(self, account_id: int) -> None:
        """Remove token from cache."""
        self._cache.pop(account_id, None)

# Global cache instance
token_cache = TokenCache(ttl_seconds=3600)  # 1 hour TTL
```

#### Option 2: Redis Cache (Production)
```python
# sync_hostaway/cache.py
import redis
from sync_hostaway.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL)

class RedisTokenCache:
    """Redis-backed token cache."""

    def __init__(self, ttl: int = 3600):
        self.ttl = ttl

    def get(self, account_id: int) -> str | None:
        """Get token from Redis."""
        key = f"token:{account_id}"
        token = redis_client.get(key)
        return token.decode() if token else None

    def set(self, account_id: int, token: str) -> None:
        """Set token in Redis with TTL."""
        key = f"token:{account_id}"
        redis_client.setex(key, self.ttl, token)

    def invalidate(self, account_id: int) -> None:
        """Delete token from Redis."""
        key = f"token:{account_id}"
        redis_client.delete(key)
```

#### Updated Auth Functions
```python
# network/auth.py
from sync_hostaway.cache import token_cache

def get_access_token(account_id: int) -> str:
    """Get token from cache first, fall back to database."""
    # Check cache
    cached = token_cache.get(account_id)
    if cached:
        logger.debug("Using cached token for account %s", account_id)
        return cached

    # Fetch from database
    with engine.connect() as conn:
        creds = get_account_credentials(conn, account_id)

    token = creds.get("access_token") if creds else None
    if token:
        # Cache for next time
        token_cache.set(account_id, token)
        return token

    # No token, refresh
    return refresh_access_token(account_id)

def refresh_access_token(account_id: int) -> str:
    """Refresh token and invalidate cache."""
    # Invalidate old cached token
    token_cache.invalidate(account_id)

    # Get new token
    new_token = create_access_token(...)
    update_access_token(conn, account_id, new_token)

    # Cache new token
    token_cache.set(account_id, new_token)

    return new_token
```

### Benefits
- **Performance:** Reduces DB queries by ~90%
- **Latency:** Faster token retrieval (memory vs DB)
- **Scalability:** Less DB load as account count grows

### Trade-offs
- **Complexity:** Additional caching layer to maintain
- **Consistency:** Cache invalidation must be correct
- **Option 1:** Simple but not distributed (multi-instance issue)
- **Option 2:** Adds Redis dependency

### Decision
**Recommended:** Start with Option 1 (in-memory), migrate to Option 2 when running multiple instances.

### Files to Create
- `sync_hostaway/cache.py` (new)
- `tests/unit/test_cache.py` (new)

### Files to Modify
- `sync_hostaway/network/auth.py`
- `requirements.txt` (add redis for Option 2)

### References
- Technical Requirements: Line 2580-2604
- Implementation Status: Line 454-470

---

## 2. Add Prometheus Metrics Endpoint

**Status:** Not implemented
**Effort:** 4-6 hours
**Impact:** Observability and monitoring

### Requirements

#### Install Dependencies
```bash
# requirements.txt
prometheus-client==0.18.0
```

#### Create Metrics Module
```python
# sync_hostaway/metrics.py (new file)
from prometheus_client import Counter, Histogram, Gauge

# Poll metrics
poll_total = Counter(
    "hostaway_polls_total",
    "Total number of polling operations",
    ["account_id", "entity_type", "status"],
)

poll_duration = Histogram(
    "hostaway_poll_duration_seconds",
    "Duration of polling operations",
    ["account_id", "entity_type"],
)

records_synced = Counter(
    "hostaway_records_synced_total",
    "Total records synced",
    ["account_id", "entity_type"],
)

# API metrics
api_requests = Counter(
    "hostaway_api_requests_total",
    "Total Hostaway API requests",
    ["endpoint", "status_code"],
)

api_latency = Histogram(
    "hostaway_api_latency_seconds",
    "Hostaway API request latency",
    ["endpoint"],
)

# Database metrics
db_operations = Counter(
    "hostaway_db_operations_total",
    "Total database operations",
    ["operation", "table"],
)

db_query_duration = Histogram(
    "hostaway_db_query_duration_seconds",
    "Database query duration",
    ["operation"],
)

# System metrics
active_accounts = Gauge(
    "hostaway_active_accounts",
    "Number of active Hostaway accounts",
)
```

#### Instrument Code
```python
# In pollers/listings.py
from sync_hostaway.metrics import poll_total, poll_duration, records_synced

def poll_listings(account_id: int) -> list[dict[str, Any]]:
    """Fetch listings with metrics."""
    with poll_duration.labels(account_id=account_id, entity_type="listings").time():
        try:
            listings = fetch_paginated("listings", account_id=account_id)
            records_synced.labels(account_id=account_id, entity_type="listings").inc(len(listings))
            poll_total.labels(account_id=account_id, entity_type="listings", status="success").inc()
            return listings
        except Exception:
            poll_total.labels(account_id=account_id, entity_type="listings", status="failure").inc()
            raise
```

#### Add Metrics Endpoint
```python
# sync_hostaway/routes/metrics.py (new file)
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

router = APIRouter()

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

#### Register Route
```python
# sync_hostaway/main.py
from sync_hostaway.routes.metrics import router as metrics_router

app.include_router(metrics_router, tags=["Metrics"])
```

### Example Metrics Output
```
# HELP hostaway_polls_total Total number of polling operations
# TYPE hostaway_polls_total counter
hostaway_polls_total{account_id="12345",entity_type="listings",status="success"} 42.0

# HELP hostaway_poll_duration_seconds Duration of polling operations
# TYPE hostaway_poll_duration_seconds histogram
hostaway_poll_duration_seconds_bucket{account_id="12345",entity_type="listings",le="0.5"} 10.0
hostaway_poll_duration_seconds_bucket{account_id="12345",entity_type="listings",le="1.0"} 35.0
...

# HELP hostaway_records_synced_total Total records synced
# TYPE hostaway_records_synced_total counter
hostaway_records_synced_total{account_id="12345",entity_type="listings"} 1234.0
```

### Grafana Dashboard (Example Queries)
```promql
# Poll success rate
sum(rate(hostaway_polls_total{status="success"}[5m])) /
sum(rate(hostaway_polls_total[5m]))

# Average poll duration
histogram_quantile(0.95, rate(hostaway_poll_duration_seconds_bucket[5m]))

# Records synced per minute
sum(rate(hostaway_records_synced_total[1m])) by (entity_type)
```

### Files to Create
- `sync_hostaway/metrics.py` (new)
- `sync_hostaway/routes/metrics.py` (new)

### Files to Modify
- `requirements.txt` (add prometheus-client)
- `sync_hostaway/main.py` (register route)
- All pollers (add instrumentation)
- All database writers (add instrumentation)

### References
- Technical Requirements: Line 1840-1849
- Implementation Status: Line 1162-1168

---

## 3. Implement FastAPI Dependency Injection for Engine

**Status:** Singleton engine imported directly
**Effort:** 3-4 hours
**Impact:** Better testability

### Current Pattern (Global Import)
```python
# routes/accounts.py
from sync_hostaway.db.engine import engine  # Global import

def create_account(...):
    with engine.connect() as conn:  # Uses global
        ...
```

### Proposed Pattern (Dependency Injection)

#### Create Dependency
```python
# sync_hostaway/dependencies.py (new file)
from typing import Generator
from sqlalchemy import Engine
from sync_hostaway.db.engine import engine

def get_db_engine() -> Generator[Engine, None, None]:
    """Dependency for database engine."""
    yield engine
```

#### Use in Routes
```python
# routes/accounts.py
from fastapi import Depends
from sqlalchemy import Engine
from sync_hostaway.dependencies import get_db_engine

@router.post("/accounts")
def create_account(
    payload: AccountCreatePayload,
    background_tasks: BackgroundTasks,
    engine: Engine = Depends(get_db_engine),  # Injected
) -> dict[str, Any]:
    """Create account."""
    with engine.connect() as conn:
        ...
```

#### Testing with Mocks
```python
# tests/unit/routes/test_accounts.py
from unittest.mock import Mock
from fastapi.testclient import TestClient

def test_create_account():
    """Test account creation with mocked engine."""
    mock_engine = Mock(spec=Engine)

    # Override dependency
    app.dependency_overrides[get_db_engine] = lambda: mock_engine

    client = TestClient(app)
    response = client.post("/hostaway/accounts", json={...})

    assert response.status_code == 201
    mock_engine.connect.assert_called_once()
```

### Benefits
- **Testability:** Easy to inject mock engine in tests
- **Flexibility:** Can swap engine implementations
- **Best Practice:** Follows FastAPI patterns

### Trade-offs
- **Verbosity:** More boilerplate in route signatures
- **Learning Curve:** Team must understand dependency injection

### Decision
**Recommended:** Implement for new routes, migrate existing routes gradually

### Files to Create
- `sync_hostaway/dependencies.py` (new)

### Files to Modify
- All route handlers (add Depends)
- All route tests (use dependency overrides)

### References
- Implementation Status: Line 1020-1037
- FastAPI Dependency Injection docs

---

## 4. Add Incremental Sync Logic

**Status:** FULL and DIFFERENTIAL modes defined but not differentiated
**Effort:** 4-6 hours
**Impact:** Efficiency for large datasets

### Current State
Both FULL and DIFFERENTIAL modes fetch all data:
```python
# services/sync.py
def sync_account(account_id: int, mode: SyncMode, dry_run: bool = False):
    # Mode parameter ignored - always fetches everything
    listings = poll_listings(account_id=account_id)
    ...
```

### Incremental Sync Design

#### Add `updated_since` Parameter
```python
# pollers/listings.py
def poll_listings(
    account_id: int,
    updated_since: datetime | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch listings, optionally filtered by update time.

    Args:
        account_id: Hostaway account ID
        updated_since: Only fetch listings updated after this time

    Returns:
        List of listings
    """
    endpoint = "listings"

    if updated_since:
        # Hostaway API supports updatedSince parameter
        endpoint += f"?updatedSince={updated_since.isoformat()}"

    return fetch_paginated(endpoint, account_id=account_id)
```

#### Implement Differential Mode
```python
# services/sync.py
def sync_account(account_id: int, mode: SyncMode, dry_run: bool = False):
    """Sync account with mode support."""
    logger.info("Starting %s sync for account %s", mode, account_id)

    # Determine time window
    updated_since = None
    if mode == SyncMode.DIFFERENTIAL:
        # Fetch last_sync_at from database
        with engine.connect() as conn:
            account = get_account_with_sync_status(conn, account_id)
            if account and account["last_sync_at"]:
                updated_since = account["last_sync_at"]
                logger.info("Differential sync since %s", updated_since)

    # Poll with time filter
    listings = poll_listings(account_id=account_id, updated_since=updated_since)
    insert_listings(account_id, listings, engine, dry_run)

    # Same for reservations and messages
    ...
```

### Benefits
- **Performance:** Fetches only changed records
- **Efficiency:** Reduces API calls and bandwidth
- **Scalability:** Better for large accounts

### Requirements
- Hostaway API must support `updatedSince` parameter (verify in docs)
- `last_sync_at` timestamp must be reliable

### Files to Modify
- `sync_hostaway/pollers/listings.py`
- `sync_hostaway/pollers/reservations.py`
- `sync_hostaway/pollers/messages.py`
- `sync_hostaway/services/sync.py`

### References
- Technical Requirements: Line 2281-2299
- SyncMode enum definition

---

## 5. Add Request ID Tracing

**Status:** No request tracing
**Effort:** 2-3 hours
**Impact:** Debugging and log correlation

### Implementation

#### Generate Request IDs
```python
# sync_hostaway/middleware.py (new file)
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Add to response headers
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response
```

#### Add to App
```python
# sync_hostaway/main.py
from sync_hostaway.middleware import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)
```

#### Include in Logs
```python
# With structured logging
logger.info(
    "account_created",
    account_id=123,
    request_id=request.state.request_id,  # Include in all logs
)
```

#### Access in Routes
```python
@router.post("/accounts")
def create_account(request: Request, ...):
    request_id = request.state.request_id
    logger.info("Creating account", request_id=request_id)
    ...
```

### Benefits
- **Debugging:** Trace single request through logs
- **Correlation:** Link frontend → backend → database operations
- **Monitoring:** Track request flows in distributed systems

### Files to Create
- `sync_hostaway/middleware.py` (new)

### Files to Modify
- `sync_hostaway/main.py` (add middleware)
- Update logging calls to include request_id

### References
- Technical Requirements: Line 1771
- CONTRIBUTING.md: Logging section

---

## Summary

| Task | Effort | Impact | Complexity |
|------|--------|--------|------------|
| Token cache service | 6-8 hrs | Performance | Medium |
| Prometheus metrics | 4-6 hrs | Observability | Medium |
| DI for engine | 3-4 hrs | Testability | Low |
| Incremental sync | 4-6 hrs | Efficiency | Medium |
| Request ID tracing | 2-3 hrs | Debugging | Low |

**Total P3 Effort:** 18-24 hours

---

## Recommended Order

1. **Request ID tracing** (2-3 hrs) - Quick debugging improvement
2. **DI for engine** (3-4 hrs) - Improves testability
3. **Incremental sync** (4-6 hrs) - Performance for large accounts
4. **Prometheus metrics** (4-6 hrs) - Observability foundation
5. **Token cache service** (6-8 hrs) - Advanced optimization

---

## When to Implement P3 Tasks

Consider these tasks when:
- **Token cache:** Account count > 50 or API call volume is high
- **Metrics:** Setting up production monitoring with Grafana/Prometheus
- **DI pattern:** Writing extensive unit tests for routes
- **Incremental sync:** Accounts have > 1000 listings/reservations
- **Request tracing:** Debugging complex multi-step workflows

---

## Backlog

Additional ideas not fully scoped:
- Circuit breaker pattern for Hostaway API
- Feature flags (LaunchDarkly, etc.)
- Canary deployment support
- Advanced retry strategies (exponential backoff with jitter)
- Webhook signature validation
- Multi-region deployment support
- Data retention policies and archival
- GraphQL API layer
- OpenTelemetry distributed tracing

---

**Priority:** These tasks are optimizations - focus on P0/P1/P2 first!
