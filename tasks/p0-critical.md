# P0 - Critical Tasks (Blocking Development)

**Priority:** Highest - These issues block development or cause runtime errors

**Last Updated:** 2025-10-21

---

## ✅ Recently Completed (2025-10-21)

1. **Fix Test Environment** - Tests now run (PYTHONPATH configured, dependencies installed)
2. **Fix SyncMode.INCREMENTAL** - Removed SyncMode entirely (differential sync not beneficial)
3. **Fix ALLOWED_ORIGINS Type Issues** - Proper type annotations in config.py and main.py

**Mypy improvements:** 9 errors → 6 errors (3 P0 blockers fixed)

---

## 1. Complete Webhook Implementation

**Status:** 🚨 10% Complete - Real-time sync non-functional
**Effort:** TBD (needs research first)
**Impact:** Enables real-time webhook-driven sync

### Current State

Basic endpoint exists but minimal functionality:
```python
# sync_hostaway/routes/webhook.py (current)
@router.post("/hostaway")  # Should rename to just "/webhooks"
async def receive_hostaway_webhook(request: Request) -> JSONResponse:
    payload = await request.json()
    event_type = payload.get("eventType")
    logger.info("Received webhook: %s", event_type)
    # 🧪 TODO: Dispatch to sync handler  ← NEEDS IMPLEMENTATION
    return JSONResponse(content={"status": "accepted"})
```

### What We Need to Research First

Before implementing, we need to understand:

1. **Hostaway Webhook Authentication**
   - What authentication methods does Hostaway support?
   - HTTP Basic Auth? Certificate-based? Signature validation?
   - Multiple methods per customer?
   - Where to find official documentation?

2. **Webhook Payload Structure**
   - What does the actual JSON payload look like?
   - What fields are consistent across all event types?
   - What's the full list of event types?

3. **Webhook Registration**
   - Manual configuration in Hostaway dashboard?
   - OR programmatic via Hostaway API (`POST /v1/webhooks`)?
   - When should registration happen?

4. **Webhook Lifecycle Management**
   - How does Hostaway handle failed deliveries?
   - Do webhooks get auto-disabled after N failures?
   - Do we need health monitoring?

### Proposed Simple Approach

**Phase 1: Raw Storage (Simplest)**
- Just save the entire webhook payload to a `webhooks` table (raw JSON)
- Validate authentication (whatever Hostaway uses)
- Return 200 OK quickly
- Don't process events yet - figure out schema later

**Phase 2: Processing (Later)**
- Parse event types
- Route to appropriate handlers
- Write to listings/reservations/messages tables

### Prerequisites

Before starting implementation:

1. **✅ Test current codebase** - Verify account creation + sync works after recent changes
2. **✅ Document sync performance** - Time how long full sync takes for baseline
3. **✅ Fix broken tests** - Get test suite passing and coverage up
4. **📚 Research Hostaway webhook docs** - Understand authentication, payloads, lifecycle

### Next Actions

1. Manually test account creation + sync flow
2. Document sync timing/performance
3. Fix test suite
4. Research Hostaway webhook documentation
5. Create detailed implementation plan with actual requirements

---

## Summary

| Task | Status | Next Step |
|------|--------|-----------|
| Test recent code changes | ⏳ Pending | Create account, run sync, verify works |
| Document sync performance | ⏳ Pending | Time sync duration, document for future |
| Fix test suite | ⏳ Pending | Update tests for SyncMode removal, get passing |
| Research webhooks | ⏳ Pending | Fetch Hostaway webhook docs, understand requirements |
| Implement webhooks | 🔜 Future | After research + testing complete |

---

## Current Focus

**Don't start webhook implementation yet.**

Instead:
1. Test that account creation + sync still works after code changes
2. Fix broken tests
3. Research webhook requirements properly
4. Then plan webhook implementation with actual facts

---

## References

- Implementation Status: `docs/implementation-status.md`
- Differential Sync Research: `tasks/missing-features.md` (lines 85-153)
- Technical Requirements: `docs/technical-requirements.md` (line 1472-1553)
