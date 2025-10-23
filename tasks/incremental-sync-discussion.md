# Incremental Sync: Research & Discussion

**Last Updated:** 2025-10-23
**Status:** Researched - Implementation deferred
**Priority:** P3 (Optional Optimization)

---

## Executive Summary

**Decision:** Incremental sync provides minimal benefit (2.1% API call reduction) and is NOT recommended for implementation.

**Reason:** Messages represent 98% of API calls and don't support date filtering. Webhooks are the proper solution for real-time updates.

---

## Production Performance Data

**Test Date:** 2025-10-22
**Test Account:** 59808 (787 reservations, 787 conversations)

### Actual API Call Breakdown Per Sync

| Resource | API Calls | Percentage |
|----------|-----------|------------|
| Token generation | 1 | 0.1% |
| Listings | 1 | 0.1% |
| Reservations | 8 | 1.0% |
| Conversations list | 8 | 1.0% |
| Individual messages | 787 | 97.8% |
| **TOTAL** | **805** | **100%** |

**Sync Duration:** 43 seconds (with ThreadPoolExecutor, 4 workers for messages)
**Without Concurrency:** ~402 seconds (6.7 minutes) at max rate limit

---

## API Date Filtering Support

| Endpoint | Date Filtering | Parameters |
|----------|---------------|------------|
| `/v1/listings` | ✅ YES | `latestActivityStart`, `latestActivityEnd` |
| `/v1/reservations` | ✅ YES | `latestActivityStart`, `latestActivityEnd` |
| `/v1/conversations` | ❌ NO | None available |
| `/v1/conversations/{id}/messages` | ❌ NO | None available |

---

## Why Incremental Sync Doesn't Help

### Potential Savings Analysis

**Best case scenario** with `latestActivityStart` filtering on listings and reservations:

- Listings: 1 API call → still 1 API call (filtering is server-side)
- Reservations: 8 API calls → still 8 API calls (still paginate through filtered results)
- Messages: 795 API calls → **still 795 API calls (NO FILTERING SUPPORT)**

**Potential savings:** 0 API calls out of 805 = **0% reduction**

### Benefits That Do Exist (Minor)

1. **Less data transferred** - Server returns fewer records
2. **Fewer database writes** - Only upsert changed records
3. **Slightly faster processing** - Less data to parse/normalize

### Complexity Cost

1. Track `last_sync_at` timestamps per account
2. Pass `updated_since` parameter through all pollers
3. Handle edge cases (first sync, timestamp gaps, etc.)
4. Test differential logic thoroughly

**Verdict:** Complexity cost >> minimal benefits

---

## Hostaway Rate Limits

### Per-IP Limits (Primary Constraint)
- **15 requests per 10 seconds** = 90 req/min = 5,400 req/hour = 129,600 req/day

### Per-Account Limits (Secondary)
- **20 requests per 10 seconds** = 120 req/min = 7,200 req/hour = 172,800 req/day

**Important:** Each customer syncs their **own** Hostaway account using their own `client_secret`. The per-account limit applies to **their** Hostaway account, not your system.

**Bottleneck:** Per-IP limit is the scaling constraint for multi-tenant deployments.

---

## Scaling Analysis

### Scenario 1: Hourly Full Sync (Current Implementation)

**Per customer:** 805 calls/hour
**IP hourly limit:** 5,400 calls
**Max customers per IP:** 5,400 ÷ 805 = **~6 customers**

### Scenario 2: Intelligent Polling Frequencies (RECOMMENDED)

Break up polling by data volatility:

| Resource | Frequency | Calls/Day | Reasoning |
|----------|-----------|-----------|-----------|
| Listings | 3x/day | 3 | Rarely change |
| Reservations | 1x/day | 8 | Moderate changes |
| Messages | Every 2 hours (12x/day) | 9,540 | Most time-sensitive |
| **TOTAL** | | **9,551** | |

**IP daily limit:** 129,600 calls
**Max customers per IP:** 129,600 ÷ 9,551 = **~13 customers per IP**

**Impact:** 51% reduction in API calls vs hourly sync (19,320/day → 9,551/day)

### Scenario 3: Webhook-First (IMPLEMENTED - Optimal)

With webhooks eliminating most polling:

**Daily reconciliation sync:** 1x/day full sync = 805 calls/day
**Webhook events:** Near-zero polling (webhooks push changes in real-time)

**Max customers per IP:** 129,600 ÷ 805 = **~160 customers per IP**

**Impact:** 95% reduction in API calls vs intelligent polling

---

## Multi-IP Scaling

| Scenario | Customers/IP | With 10 IPs |
|----------|--------------|-------------|
| Hourly Full Sync | 6 | 60 |
| Intelligent Polling | 13 | 130 |
| Webhook-First | 160 | 1,600 |

---

## Recommended Strategy

### Phase 1: Webhooks (DONE ✅)
- Implement complete webhook system for real-time updates
- Handles listings, reservations, messages events
- 95% reduction in polling needs

### Phase 2: Daily Reconciliation (CURRENT STATE)
- Run full sync 1x/day for data integrity
- Catches any missed webhook events
- 805 API calls per customer per day

### Phase 3: Intelligent Polling (IF NEEDED)
- Only implement if webhook delivery proves unreliable
- Stagger polling frequencies by data volatility
- Reduces API calls by 51% vs hourly sync

### Phase 4: Incremental Sync (NOT RECOMMENDED)
- Only 2.1% potential improvement
- High complexity cost
- Messages (98% of calls) can't be filtered
- **Skip this optimization**

---

## Implementation Notes (If Pursuing Despite Recommendation)

### Database Changes Needed
```sql
ALTER TABLE hostaway.accounts
ADD COLUMN last_listings_sync_at TIMESTAMP,
ADD COLUMN last_reservations_sync_at TIMESTAMP,
ADD COLUMN last_messages_sync_at TIMESTAMP;
```

### Poller Signature Changes
```python
def poll_listings(
    account_id: int,
    updated_since: datetime | None = None,  # New parameter
) -> list[dict[str, Any]]:
    endpoint = "listings"
    if updated_since:
        # Add latestActivityStart parameter
        endpoint += f"?latestActivityStart={updated_since.isoformat()}"
    return fetch_paginated(endpoint, account_id=account_id)
```

### Service Layer Changes
```python
def sync_account(account_id: int, mode: SyncMode):
    if mode == SyncMode.INCREMENTAL:
        # Fetch last sync timestamps
        with engine.connect() as conn:
            account = get_account_with_sync_status(conn, account_id)
            listings_since = account.get("last_listings_sync_at")
            reservations_since = account.get("last_reservations_sync_at")
    else:
        listings_since = None
        reservations_since = None

    listings = poll_listings(account_id, updated_since=listings_since)
    reservations = poll_reservations(account_id, updated_since=reservations_since)
    # Messages: NO FILTERING SUPPORT - always fetch all
    messages = poll_messages(account_id)
```

### Testing Requirements
- Test first sync (no last_sync_at)
- Test incremental sync with recent data
- Test incremental sync with no changes
- Test incremental sync with timestamp gaps
- Verify FULL mode still works

**Estimated Effort:** 4-6 hours

---

## References

- Technical Requirements: Line 2281-2299
- Hostaway API Docs: Rate Limits section
- Implementation Status: Polling logic fully functional
- Production Test: Account 59808 (787 reservations)

---

## Conclusion

**Webhooks solve the real-time update problem.** Daily reconciliation syncs provide data integrity with minimal API usage. Incremental sync adds complexity for negligible benefit.

**Recommendation:** Do NOT implement incremental sync. Focus on webhook reliability and monitoring instead.
