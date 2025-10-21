# Missing Features (From Technical Requirements)

**Source:** Compared actual codebase against `Hostaway-Sync-Service-Technical-Requirements.md`

**Last Updated:** 2025-10-21

---

## Critical Missing Features (P0)

### 1. Webhook Event Handlers
**Tech Doc Reference:** Line 1472-1553
**Current Status:** 25% complete (basic endpoint exists)

**Missing Components:**
- Event routing logic
- Handler functions for each event type:
  - `listing.created`
  - `listing.updated`
  - `listing.deleted`
  - `reservation.created`
  - `reservation.updated`
  - `reservation.cancelled`
  - `message.created`
- Basic Auth validation
- Deduplication mechanism
- Event signature validation

**Location:** `sync_hostaway/routes/webhook.py`

**See:** `tasks/p0-critical.md` #4 for implementation details

---

## Production Requirements Missing (P1)

### 1. Health Check Endpoints
**Tech Doc Reference:** Line 1828-1851
**Status:** Not implemented

**Required Endpoints:**
- `GET /health` - Liveness probe
- `GET /ready` - Readiness probe (with DB check)

**Impact:** Cannot deploy to Kubernetes/container orchestration

**See:** `tasks/p1-high.md` #2 for implementation details

---

### 2. Metrics/Observability
**Tech Doc Reference:** Line 1840-1849
**Status:** Not implemented

**Required:**
- Prometheus metrics endpoint
- Key metrics:
  - Poll success/failure rates
  - API latency histograms
  - Database query durations
  - Active account count
  - Records synced counters

**See:** `tasks/p3-low.md` #2 for implementation details

---

## Advanced Features Not Implemented (P3)

### 1. Token Cache Service
**Tech Doc Reference:** Line 2580-2604
**Status:** Not implemented (uses DB queries)

**Design:**
- In-memory or Redis-backed cache
- TTL-based expiration
- Cache invalidation on refresh

**Impact:** Performance optimization for high-volume accounts

**See:** `tasks/p3-low.md` #1

---

### 2. Incremental Sync Logic
**Tech Doc Reference:** Line 2281-2299
**Status:** Defined but not differentiated

**Current:** FULL and DIFFERENTIAL modes both fetch all data

**Needed:**
- Use `updatedSince` parameter in Hostaway API
- Fetch only changed records based on `last_sync_at`
- Optimize bandwidth and API calls

**See:** `tasks/p3-low.md` #4

---

### 3. Daemon Process for Multi-Account Sync
**Tech Doc Reference:** Task 4 in README (Line 131-137)
**Status:** Function exists, no scheduler

**Current:** `sync_all_accounts()` function exists but must be called manually

**Needed:**
- Scheduled background job (cron, APScheduler, Celery)
- Daily sync for all active accounts
- Error isolation per account
- Retry logic for failed accounts

**Implementation Ideas:**
```python
# Option 1: APScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(
    sync_all_accounts,
    'cron',
    hour=2,  # 2 AM daily
    args=[SyncMode.DIFFERENTIAL, False]
)

# Option 2: Celery Beat
@celery.task
def daily_sync_task():
    sync_all_accounts(SyncMode.DIFFERENTIAL)
```

---

### 4. Send Message API
**Tech Doc Reference:** Task 6 in README (Line 155-161)
**Status:** Not implemented

**Requirements:**
- `POST /send-message` endpoint
- Accept: `reservation_id`, `message`, `channel_type`
- Lookup account credentials
- Call Hostaway messaging API
- Log success/failure

**Effort:** 4-6 hours

**Design:**
```python
# routes/messages.py
@router.post("/messages")
def send_message(
    reservation_id: int,
    message: str,
    channel_type: str,
) -> dict[str, Any]:
    """Send message to guest via Hostaway."""
    # 1. Lookup reservation → account_id
    # 2. Get account token
    # 3. POST to Hostaway /conversations/{id}/messages
    # 4. Return success/failure
```

---

### 5. Webhook Authentication Validation
**Tech Doc Reference:** Line 1522-1533
**Status:** Not implemented

**Requirements:**
- HTTP Basic Auth validation
- Credentials stored in `accounts.webhook_login`, `accounts.webhook_password`
- Return 401 Unauthorized if invalid

**Already Covered:** Part of webhook implementation (P0 #4)

---

### 6. Secret Encryption
**Tech Doc Reference:** Task 5 (Line 141-151)
**Status:** Not implemented

**Current:** Credentials stored in plaintext in database

**Requirements:**
- Encrypt `client_secret` before storage
- Encrypt `access_token` before storage
- Options:
  - Database-level encryption (pgcrypto)
  - Application-level encryption (Fernet, AES)
  - Secrets manager integration (AWS Secrets Manager, HashiCorp Vault)

**Priority:** P1-P2 (security requirement for production)

**Design Considerations:**
- Key management (where to store encryption key?)
- Rotate encryption keys
- Migrate existing plaintext secrets

---

## Features Marked Complete in Tech Doc

### ✅ Implemented Features (Verified)

1. **Database Schema** ✅
   - All tables created (accounts, listings, reservations, messages)
   - Migrations working
   - Schema namespace = "hostaway"

2. **Network Client** ✅
   - Pagination working
   - Retry logic functional
   - Token refresh on 403

3. **Database Writers** ✅
   - IS DISTINCT FROM optimization
   - Upsert logic correct
   - Foreign key handling

4. **Pollers** ✅
   - Listings poller complete
   - Reservations poller complete
   - Messages poller complete

5. **Account Management API** ✅
   - POST /accounts (create) ✅
   - POST /accounts/{id}/sync (manual sync) ✅
   - GET /accounts/{id} (read) ✅
   - PUT /accounts/{id} (update) ✅
   - DELETE /accounts/{id} (delete) ✅

6. **Authentication** ✅
   - Token creation ✅
   - Token refresh ✅
   - Token storage ✅

7. **Sync Service** ✅
   - sync_account() ✅
   - sync_all_accounts() ✅
   - last_sync_at tracking ✅

---

## Summary: Features by Status

| Status | Count | Examples |
|--------|-------|----------|
| ✅ Complete | 7 | Database schema, network client, pollers, account API |
| 🔄 Partial | 2 | Webhooks (25%), Incremental sync (defined but not working) |
| ❌ Missing (P0) | 1 | Webhook event handlers |
| ❌ Missing (P1) | 2 | Health checks, secret encryption |
| ❌ Missing (P3) | 5 | Token cache, daemon scheduler, send message API, etc. |

**Overall Completion:** ~70% of critical features implemented ✅

---

## Recommendations

**Immediate (P0):**
1. Complete webhook implementation → Enables real-time sync

**Short-term (P1):**
1. Add health/readiness endpoints → Production deployment
2. Implement secret encryption → Security requirement

**Long-term (P3):**
1. Add token caching → Performance optimization
2. Implement send message API → Guest communication
3. Add scheduled daemon → Automated daily sync

---

## Cross-Reference

- **P0 Tasks:** See `tasks/p0-critical.md`
- **P1 Tasks:** See `tasks/p1-high.md`
- **P2 Tasks:** See `tasks/p2-medium.md`
- **P3 Tasks:** See `tasks/p3-low.md`
- **Implementation Status:** See `docs/implementation-status.md`
