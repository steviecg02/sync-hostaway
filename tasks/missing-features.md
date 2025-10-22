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

### 2. Differential/Incremental Sync Analysis
**Tech Doc Reference:** Line 2281-2299
**Status:** Researched and rejected
**Date:** 2025-10-21

**Research Summary:**

Investigated whether differential/incremental sync would improve performance by using date filtering parameters in the Hostaway API.

**API Support Analysis:**
- ✅ `/v1/listings` - Has `latestActivityStart` and `latestActivityEnd` parameters
- ✅ `/v1/reservations` - Has `latestActivityStart` and `latestActivityEnd` parameters
- ❌ `/v1/conversations` - NO date filtering available
- ❌ `/v1/conversations/{id}/messages` - NO date filtering available

**Actual API Call Breakdown (Account 59808 - Production Test):**
- Token generation: 1 API call
- Listings: 1 API call (7 listings, 1 page)
- Reservations: 8 API calls (787 reservations, 8 pages)
- Conversations list: 8 API calls (787 conversations, 8 pages)
- Individual conversation messages: 787 API calls (1 per conversation)
- **Total: 805 API calls per sync**
- **Actual duration: 43 seconds** (with ThreadPoolExecutor, 4 workers for messages)

**Why Differential Doesn't Help:**

Even with `latestActivityStart` filtering on listings and reservations:
- **Still make the same number of API calls** (filtering happens server-side, but you still request the pages)
- Only benefit would be less data returned and fewer database writes
- **Messages represent 98% of API calls** (795 out of 805) and don't support date filtering at all
- **Potential savings: 17 API calls out of 805 = 2.1% improvement**

This minimal improvement doesn't justify the added code complexity.

**Rate Limits (from Hostaway API docs):**
- 15 requests per 10 seconds per IP address (90 req/min = 5,400/hour = 129,600/day)
- 20 requests per 10 seconds per account ID (120 req/min = 7,200/hour = 172,800/day)

**Current Performance (Measured with Account 59808):**
- **805 API calls per sync**
- **43 seconds per sync** (with concurrency)
- **Without concurrency:** ~402 seconds (6.7 minutes) at max rate limit

**Conclusion:**

Differential sync provides no meaningful performance benefit given:
1. Messages are the bottleneck (98% of API calls) and can't be filtered
2. Filtering listings/reservations still requires making the API calls
3. Webhooks are the proper solution for real-time updates

---

## Scaling Analysis (Based on Production Metrics)

**Test Date:** 2025-10-22
**Test Account:** 59808 (787 reservations)

### Scenario 1: Hourly Full Sync (Current Implementation)

**Per customer:** 805 calls/hour

**Constraint:** Per-IP rate limit of 90 req/min (5,400 req/hour)

**Max customers per IP (hourly sync):** 5,400 ÷ 805 = **~6 customers**

### Scenario 2: Intelligent Polling Frequencies (Recommended)

Break up polling by data volatility:

**Listings:** 3x/day (rarely change)
- 1 call × 3 = 3 calls/day

**Reservations:** 1x/day (moderate changes)
- 8 calls × 1 = 8 calls/day

**Messages:** Every 2 hours = 12x/day (most time-sensitive)
- (8 conversations + 787 messages) × 12 = **9,540 calls/day**

**Total per customer/day:** ~9,551 calls

**Daily IP limit:** 129,600 calls/day

**Max customers per IP:** 129,600 ÷ 9,551 = **~13 customers per IP**

### Scenario 3: Webhook-First (Future - P0 Task)

With webhooks eliminating most polling:

**Daily reconciliation sync:** 1x/day full sync
- 805 calls × 1 = 805 calls/day

**Webhook events:** Near-zero polling (webhooks push changes)

**Max customers per IP:** 129,600 ÷ 805 = **~160 customers per IP**

### Multi-IP Scaling

- **Single IP:** 13 customers (intelligent polling) or 160 customers (webhooks)
- **Load balancer with multiple IPs:** 13N or 160N customers
- **Example:** 10 IPs = 130 customers (polling) or 1,600 customers (webhooks)

### Important Note on Per-Account Rate Limits

Each customer syncs their **own** Hostaway account (using their own `client_secret`). The per-account rate limit (120 req/min) applies to **their** Hostaway account, not your system.

**This means:**
- The **per-IP limit is the bottleneck** for multi-tenant scaling
- Individual customers won't hit their per-account limits with intelligent polling
- Webhooks are critical for scaling beyond ~13 customers per IP

**Future Optimization Options (if needed):**

If scaling becomes an issue, consider:

1. **Intelligent polling intervals** (RECOMMENDED - see Scenario 2 above)
   - Listings: 2-3x/day (rarely change, low volume)
   - Reservations: 1-2x/day (moderate changes)
   - Messages: Every 1-2 hours (highest volume, most time-sensitive)
   - **Impact:** 51% reduction in API calls (19,320/day → 9,551/day)

2. **Webhook implementation** (P0 TASK - see below)
   - Eliminates 99% of polling
   - Only need occasional full syncs for reconciliation
   - **Impact:** 96% reduction in API calls (19,320/day → 805/day)

3. **Multiple IPs with load balancing**
   - Deploy sync workers across multiple IPs
   - Each IP supports ~13 customers (intelligent polling) or ~160 (webhooks)

4. **Global rate limiter**
   - Process multiple accounts in parallel while respecting per-IP limits
   - Coordinate across workers to stay under 90 req/min per IP

**Implementation Decision:**

- **SyncMode enum removed entirely** (no DIFFERENTIAL or INCREMENTAL)
- Only full sync supported
- Webhooks are the primary mechanism for real-time updates
- Full syncs serve as backup/catch-up mechanism

---

## Production Testing Results (2025-10-22)

**Test Account:** 59808 (787 reservations)
**Test Type:** Full sync with messages

**Actual Performance:**
- **805 API calls in 43 seconds**
- **Calculated rate:** 1,122 requests/minute
- **Expected if rate limited:** 6.7 minutes at 120 req/min

**Finding:** Hostaway's documented rate limits (90 req/min per IP, 120 req/min per account) were **not enforced** during testing.

**Possible explanations:**
1. Rate limits not enforced at current scale
2. Burst allowances or token bucket algorithm
3. Documentation outdated
4. Soft limits (throttling) vs hard limits (429 errors)

**Implication:** Current concurrent implementation (ThreadPoolExecutor with 4 workers) works without hitting rate limits. Scaling projections based on documented limits may be overly conservative.

**Monitoring:** Watch for 429 (rate limit) responses in production. Retry logic already implemented in `sync_hostaway/network/client.py`.

---

## Recommended Implementation Strategy

### Phase 1: Initial Account Sync (Current)

**When:** Account is first created/onboarded

**What to sync:**
- ✅ Listings (full historical data)
- ✅ Reservations (full historical data)
- ✅ Messages (full historical data)

**API calls:** ~805 calls (43 seconds with concurrency)

**Rationale:** Get complete historical data for new customer

---

### Phase 2: Nightly Reconciliation Sync (Recommended Change)

**When:** Every night (scheduled background job)

**What to sync:**
- ✅ Listings (catch missed webhook events)
- ✅ Reservations (catch missed webhook events)
- ❌ **Messages (EXCLUDED - webhooks handle real-time updates)**

**API calls:** ~10 calls per account per night (98.8% reduction)

**Rationale:**
- Messages are 98% of API calls (795 out of 805)
- Webhooks provide real-time message updates
- Nightly sync is just a safety net for missed webhooks
- Massively reduces API load

**Scaling impact:**
- Daily IP limit: 129,600 calls (if enforced)
- Per-account nightly sync: 10 calls
- **Max customers per IP:** 129,600 ÷ 10 = **~1,296 customers**

---

### Phase 3: If Webhook Reliability Issues

**If:** Webhooks prove unreliable and messages must be added back to nightly sync

**Then implement one of:**

**Option A: Intelligent Polling (10-50 customers)**
- Stagger sync times across accounts
- Use APScheduler or similar
- Single worker, sequential processing
- Handles ~13 customers per IP with messages included (if rate limits enforced)

**Option B: Multi-Worker with Task Queue (50+ customers)**
- Deploy Celery + Redis
- Multiple workers on different IPs
- Each worker: ~13 customers
- Horizontal scaling: Add workers on new IPs as needed

**Option C: Rate Limit Coordination (Only if hitting 429s)**
- Workers coordinate via Redis counters
- Respect per-IP limits across workers
- Adds latency, only needed if rate limits enforced

**Decision criteria:**
- **<10 customers:** Do nothing, monitor 429s
- **10-50 customers:** Option A (intelligent polling)
- **50+ customers:** Option B (multi-worker)
- **Hitting 429s consistently:** Option C (add coordination)

---

## Current Status & Next Steps

**Current implementation:**
- ✅ Full sync working (805 calls in 43 seconds)
- ✅ Concurrent message fetching (ThreadPoolExecutor, 4 workers)
- ✅ Retry logic for transient failures
- ❌ No nightly reconciliation sync scheduled yet
- ❌ Webhooks not implemented (P0 task)

**Recommended next steps:**
1. **Implement nightly reconciliation sync** (listings + reservations only, exclude messages)
2. **Implement webhooks** (P0 task) for real-time updates
3. **Monitor 429 responses** in production logs
4. **Re-evaluate at scale:** If webhook reliability requires adding messages back to nightly sync, choose Option A/B/C based on customer count

**References:**
- Hostaway API docs: https://api.hostaway.com/documentation
- Related code: `sync_hostaway/pollers/messages.py` (lines 35-65 show nested API call pattern)
- Rate limit retry logic: `sync_hostaway/network/client.py`

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
| 🔄 Partial | 1 | Webhooks (25%) |
| ❌ Missing (P0) | 1 | Webhook event handlers |
| ❌ Missing (P1) | 2 | Health checks, secret encryption |
| ❌ Missing (P3) | 4 | Token cache, daemon scheduler, send message API |
| 🚫 Rejected | 1 | Differential/incremental sync (researched, not worth implementing) |

**Overall Completion:** ~70% of critical features implemented ✅

**Note:** Differential sync was removed after research showed it provides no meaningful benefit (1.4% API call reduction). Webhooks are the primary real-time mechanism.

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
