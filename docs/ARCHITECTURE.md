# sync-hostaway Architecture

**Last Updated:** 2025-10-21
**Status:** Production-grade implementation (70% complete)

---

## Overview

The Hostaway Sync Service is a **multi-tenant data synchronization service** that polls the Hostaway API to sync listings, reservations, and message threads into a local PostgreSQL database. The service replaces direct Hostaway dependency with a local data layer optimized for fast queries.

**Key Characteristics:**
- Multi-tenant: Supports multiple Hostaway accounts
- Real-time: Webhook-driven updates + scheduled full syncs
- Efficient: IS DISTINCT FROM optimization prevents unnecessary writes
- Resilient: Automatic retry logic, token refresh, rate limiting
- API-first: FastAPI endpoints for account management and webhooks

---

## Multi-PMS Design Philosophy

### Why "sync-hostaway" and not "hostaway-sync"?

This service is **one component** of a larger multi-PMS synchronization platform.

**Vision:**
```
┌─────────────────┐
│ sync-hostaway   │ → stores in `hostaway` schema
├─────────────────┤
│ sync-guesty     │ → stores in `guesty` schema (future)
├─────────────────┤
│ sync-hospitable │ → stores in `hospitable` schema (future)
└─────────────────┘
         ↓
┌─────────────────┐
│ Normalization   │ → transforms to `core` schema (future)
│ Service         │ → provides unified multi-PMS API
└─────────────────┘
```

**Design Principles:**
1. **Raw Data Storage**: Each sync service stores complete API payloads AS-IS
2. **Schema Isolation**: Each PMS gets its own PostgreSQL schema (`hostaway`, `guesty`)
3. **Defer Normalization**: Normalization happens in a separate service, not at sync time
4. **Future-Proof**: Easy to add new PMS providers without touching existing services

**Current Status:**
- ✅ `hostaway` schema implemented
- ❌ Other PMS services not yet built
- ❌ Normalization service not yet built

**Reference:** `docs/technical-requirements.md` Lines 64-117

---

## System Architecture

### High-Level Components

```
┌──────────────────────────────────────────────────────┐
│                  FastAPI Application                  │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │  Account   │  │  Webhook   │  │    Health    │  │
│  │  Routes    │  │  Receiver  │  │    Checks    │  │
│  └────────────┘  └────────────┘  └──────────────┘  │
│         │               │                │          │
│  ┌──────────────────────────────────────────────┐  │
│  │          Sync Service Layer                   │  │
│  │  (Orchestrates polling & database writes)     │  │
│  └──────────────────────────────────────────────┘  │
│         │                                           │
│  ┌──────────────────────────────────────────────┐  │
│  │             Polling Layer                     │  │
│  │  • poll_listings()                            │  │
│  │  • poll_reservations()                        │  │
│  │  • poll_messages()                            │  │
│  └──────────────────────────────────────────────┘  │
│         │                                           │
│  ┌──────────────────────────────────────────────┐  │
│  │          Network Client Layer                 │  │
│  │  • fetch_paginated() - concurrent fetching    │  │
│  │  • fetch_page() - retry logic, rate limiting  │  │
│  │  • Authentication & token refresh             │  │
│  └──────────────────────────────────────────────┘  │
│         │                                           │
│  ┌──────────────────────────────────────────────┐  │
│  │         Database Writers Layer                │  │
│  │  • insert_listings() - IS DISTINCT FROM       │  │
│  │  • insert_reservations() - smart upserts      │  │
│  │  • insert_messages()                          │  │
│  │  • Account management (CRUD)                  │  │
│  └──────────────────────────────────────────────┘  │
│         │                                           │
└─────────┼───────────────────────────────────────────┘
          │
          ↓
┌──────────────────────────────────────────────────────┐
│              PostgreSQL Database                      │
│              Schema: hostaway                         │
├──────────────────────────────────────────────────────┤
│  accounts     │ Account credentials & tokens         │
│  listings     │ Property listings (raw JSONB)        │
│  reservations │ Booking reservations (raw JSONB)     │
│  messages     │ Guest message threads (raw JSONB)    │
└──────────────────────────────────────────────────────┘
```

---

## Database Schema

### Core Tables

#### `hostaway.accounts`
**Purpose:** Store Hostaway account credentials and state

| Column | Type | Description |
|--------|------|-------------|
| `account_id` | INTEGER (PK) | Hostaway account ID |
| `customer_id` | UUID | Internal customer ID (multi-tenant) |
| `client_secret` | VARCHAR | Hostaway OAuth secret |
| `access_token` | VARCHAR | Current bearer token |
| `webhook_login` | VARCHAR | Basic auth username for webhooks |
| `webhook_password` | VARCHAR | Basic auth password for webhooks |
| `is_active` | BOOLEAN | Whether to sync this account |
| `last_sync_at` | TIMESTAMP | Last successful full sync |
| `created_at` | TIMESTAMP | Account creation time |
| `updated_at` | TIMESTAMP | Last modification time |

**Indexes:** `account_id` (PK), `customer_id`

---

#### `hostaway.listings`
**Purpose:** Store property listings

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Hostaway listing ID |
| `account_id` | INTEGER (FK) | Owner account → CASCADE delete |
| `customer_id` | UUID | Internal customer ID |
| `raw_payload` | JSONB | Complete Hostaway API response |
| `created_at` | TIMESTAMP | First sync time |
| `updated_at` | TIMESTAMP | Last modification time |

**Indexes:** `id` (PK), `account_id`, `customer_id`

**Upsert Strategy:** `ON CONFLICT (id) DO UPDATE ... WHERE raw_payload IS DISTINCT FROM excluded.raw_payload`

---

#### `hostaway.reservations`
**Purpose:** Store booking reservations

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Hostaway reservation ID |
| `account_id` | INTEGER (FK) | Owner account → CASCADE delete |
| `customer_id` | UUID | Internal customer ID |
| `listing_id` | INTEGER (FK) | Property listing → CASCADE delete |
| `raw_payload` | JSONB | Complete Hostaway API response |
| `created_at` | TIMESTAMP | First sync time |
| `updated_at` | TIMESTAMP | Last modification time |

**Indexes:** `id` (PK), `account_id`, `customer_id`, `listing_id`

---

#### `hostaway.messages`
**Purpose:** Store guest message threads

| Column | Type | Description |
|--------|------|-------------|
| `reservation_id` | INTEGER (PK, FK) | Reservation ID (one thread per reservation) |
| `account_id` | INTEGER (FK) | Owner account → CASCADE delete |
| `customer_id` | UUID | Internal customer ID |
| `raw_messages` | JSONB | Array of messages (sorted by sent_at) |
| `created_at` | TIMESTAMP | First sync time |
| `updated_at` | TIMESTAMP | Last modification time |

**Indexes:** `reservation_id` (PK), `account_id`, `customer_id`

**Note:** No `listing_id` column (messages link directly to reservation)

---

## API Endpoints

### Account Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/hostaway/accounts` | Create account + trigger background sync |
| GET | `/hostaway/accounts/{id}` | Get account details with sync status |
| PUT | `/hostaway/accounts/{id}` | Update account credentials |
| DELETE | `/hostaway/accounts/{id}?hard=true` | Soft or hard delete account |
| POST | `/hostaway/accounts/{id}/sync` | Manually trigger sync (full/incremental) |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/hostaway/webhooks/hostaway` | Receive Hostaway webhook events |

**Event Types Supported (Future):**
- `listing.created`, `listing.updated`, `listing.deleted`
- `reservation.created`, `reservation.updated`, `reservation.cancelled`
- `message.created`

### Health (Future)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (checks DB) |

---

## Key Design Patterns

### 1. IS DISTINCT FROM Optimization

**Problem:** Unnecessary database writes cause `updated_at` changes even when data hasn't changed.

**Solution:** Only update when raw payload actually differs.

```python
stmt = insert(Listing).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=["id"],
    set_={
        "raw_payload": stmt.excluded.raw_payload,
        "updated_at": stmt.excluded.updated_at,
    },
    where=Listing.raw_payload.is_distinct_from(stmt.excluded.raw_payload),
    # ↑ Only updates if payload changed
)
```

**Benefits:**
- Reduces unnecessary writes
- Preserves accurate `updated_at` timestamps
- Enables efficient change detection

**Reference:** All database writers (`db/writers/`)

---

### 2. Explicit Account ID (Critical Bug Fix)

**Problem:** Early implementation extracted `accountId` from API payload. Hostaway's API doesn't always include this field.

**Solution:** Pass `account_id` explicitly as function parameter.

```python
# ❌ OLD (WRONG)
def insert_listings(engine: Engine, data: list[dict]) -> None:
    for listing in data:
        account_id = listing.get("accountId")  # May be None!
        ...

# ✅ NEW (CORRECT)
def insert_listings(engine: Engine, account_id: int, data: list[dict]) -> None:
    # account_id comes from function parameter, not payload
    ...
```

**Impact:** Prevents NULL account_id constraint violations

**Reference:** `docs/technical-requirements.md` Line 1165-1189

---

### 3. Smart Retry Logic

**Retry Conditions:**
- `429 Too Many Requests` (rate limit)
- `5xx Server Errors` (Hostaway API issues)
- `requests.Timeout` (network issues)
- `403 Forbidden` → triggers token refresh

**Does NOT Retry:**
- `400 Bad Request` (client error, won't fix itself)
- `404 Not Found` (resource doesn't exist)
- `422 Unprocessable Entity` (validation error)

**Implementation:**
```python
# network/client.py
def should_retry(res: requests.Response | None, err: Exception | None) -> bool:
    if res and res.status_code == 429:
        return True  # Rate limit
    if res and 500 <= res.status_code < 600:
        return True  # Server error
    if isinstance(err, requests.Timeout):
        return True  # Network timeout
    return False
```

**Reference:** `sync_hostaway/network/client.py:26-43`

---

### 4. Pagination Bug Fix (Critical)

**Hostaway API Uses:** `offset` parameter (not `page`)

**Bug:** Original implementation sent `page=N` instead of `offset=N*limit`

**Fix:**
```python
# ❌ OLD (WRONG)
params = {"limit": 100, "page": page_number}

# ✅ NEW (CORRECT)
params = {
    "limit": limit,
    "offset": page_number * limit,  # Calculate offset
}
```

**Reference:** `docs/technical-requirements.md` Line 883-918

---

### 5. Concurrent Page Fetching

**Strategy:** Fetch first page, determine total pages, fetch remaining pages concurrently.

```python
def fetch_paginated(endpoint: str, account_id: int, limit: int = 100) -> list[dict]:
    # 1. Fetch first page (sequential)
    first_page, _ = fetch_page(endpoint, token, page_number=0, limit=limit)
    results = first_page.get("result", [])
    total_count = first_page.get("count", len(results))
    total_pages = ceil(total_count / limit)

    # 2. Fetch remaining pages (concurrent)
    if total_pages > 1:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(fetch_page, endpoint, token, page_number=i, limit=limit)
                for i in range(1, total_pages)
            ]
            for future in as_completed(futures):
                page_data, _ = future.result()
                results.extend(page_data.get("result", []))

    return results
```

**Benefits:**
- 4x faster for large datasets
- Respects rate limits (max 4 concurrent)
- Falls back to sequential on errors

**Reference:** `sync_hostaway/network/client.py:119-156`

---

## Data Flow

### Full Sync Workflow

```
1. User: POST /hostaway/accounts
   → Create account in database
   → Schedule background task: sync_account(account_id, mode=FULL)

2. sync_account() orchestrates:
   a. poll_listings(account_id)
      → fetch_paginated("listings", account_id)
      → Returns list of raw listing dicts

   b. insert_listings(engine, account_id, listings)
      → Upserts with IS DISTINCT FROM
      → Only writes if payload changed

   c. poll_reservations(account_id)
      → Same pattern as listings

   d. poll_messages(account_id)
      → Fetches messages per reservation
      → Normalizes and sorts by sent_at

   e. insert_messages(engine, account_id, messages)
      → Upserts message threads

   f. Update accounts.last_sync_at = NOW()

3. Return success
```

---

### Webhook Update Workflow (Future)

```
1. Hostaway sends: POST /hostaway/webhooks/hostaway
   {
     "eventType": "reservation.updated",
     "accountId": 12345,
     "data": { reservation payload }
   }

2. Webhook handler validates:
   → Check Basic Auth (webhook_login, webhook_password)
   → Validate event signature (future)

3. Route event to handler:
   → handle_reservation_updated(payload)
   → insert_reservations(engine, account_id, [payload])
   → Only updates if payload changed (IS DISTINCT FROM)

4. Return 200 OK
```

**Status:** Basic endpoint exists, event handlers not implemented (P0)

---

## Technology Stack

**Language:** Python 3.11+

**Web Framework:** FastAPI 0.116.1

**Database:** PostgreSQL 15 (`hostaway` schema)

**ORM:** SQLAlchemy 2.0.41 (ORM for models, Core for bulk operations)

**Migrations:** Alembic 1.16.4

**HTTP Client:** requests 2.31.0 + httpx 0.28.1

**Deployment:** Docker + Docker Compose

**Development Tools:**
- Black (code formatting)
- Ruff (linting)
- Mypy (type checking, strict mode)
- Pytest (testing)
- Pre-commit hooks

---

## Testing Strategy

**Test Organization:**
```
tests/
├── unit/           # Fast, isolated, mocked dependencies
│   ├── network/    # Client, auth tests
│   ├── normalizers/
│   └── pollers/
├── integration/    # Real DB, mocked external APIs
│   ├── db/         # Database writer tests
│   ├── network/    # Auth integration tests
│   └── services/   # Sync service tests
└── functional/     # Full feature workflows (future)
```

**Coverage Targets:**
- Overall: 80% minimum
- Core modules: 90% (client, auth, writers, services)

**Current Status:** ⚠️ Tests exist but cannot run (ModuleNotFoundError) - **P0 fix required**

**Reference:** `tasks/p0-critical.md` #1

---

## Production Considerations

### Security
- [ ] **P1:** Encrypt `client_secret` and `access_token` before storage
  - Options: pgcrypto (DB-level) or AWS Secrets Manager
- [ ] **P1:** Implement webhook Basic Auth validation
- [ ] **P2:** Add webhook signature validation

### Reliability
- [ ] **P1:** Add health/readiness endpoints for Kubernetes
- [ ] **P2:** Implement circuit breaker for Hostaway API
- [ ] **P3:** Add request ID tracing for debugging

### Performance
- [ ] **P3:** Token caching (Redis or in-memory)
- [ ] **P3:** Connection pooling configuration
- [ ] **P3:** Incremental sync implementation (use `updatedSince` param)

### Observability
- [ ] **P1:** Structured logging (structlog)
- [ ] **P3:** Prometheus metrics endpoint
- [ ] **P3:** OpenTelemetry distributed tracing

**Reference:** `tasks/p1-high.md`, `tasks/p3-low.md`

---

## Deployment

### Local Development

```bash
# Start services
docker-compose up -d

# Run migrations
alembic upgrade head

# Start FastAPI
make run-api
```

### Production (Future)

**Recommended Stack:**
- **Container:** Docker
- **Orchestration:** Kubernetes
- **Web Server:** Gunicorn + Uvicorn workers
- **Database:** Managed PostgreSQL (RDS, Cloud SQL)
- **Secrets:** AWS Secrets Manager or HashiCorp Vault

---

## Future Enhancements

### Short-Term (P1)
1. Complete webhook event handlers
2. Add health/readiness endpoints
3. Implement secret encryption
4. Achieve 80% test coverage

### Medium-Term (P2)
1. Add CI/CD pipeline (GitHub Actions)
2. Implement structured logging
3. Refactor long functions in routes/accounts.py

### Long-Term (P3)
1. Token caching service (Redis)
2. Prometheus metrics
3. Incremental sync logic
4. Multi-PMS normalization service

**Reference:** `tasks/` directory for detailed task breakdown

---

## Related Documentation

- **Detailed Requirements:** `docs/technical-requirements.md` (comprehensive 2,800+ line spec)
- **Implementation Status:** `docs/implementation-status.md` (current state audit)
- **Contributing Guide:** `CONTRIBUTING.md` (code standards)
- **Task Tracking:** `tasks/` directory (organized by priority)
- **Claude Instructions:** `CLAUDE.md` (for future Claude Code sessions)

---

**Document Maintained By:** Stephen Guilfoil
**Last Review:** 2025-10-21
**Next Review:** After P0 tasks complete
