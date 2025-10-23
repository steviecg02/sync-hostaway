# Webhook System Completion

**Status:** In Progress (25% complete)
**Priority:** High
**Updated:** 2025-10-23

---

## Current State

### ✅ Completed

1. **Basic Webhook Endpoint** (`sync_hostaway/routes/webhook.py`)
   - HTTP Basic Auth validation
   - Request validation (eventType, accountId)
   - Account existence checking
   - Returns 200 for all valid requests

2. **Webhook Registration Service** (`sync_hostaway/services/webhook_registration.py`)
   - `register_webhook(account_id)` - Registers unified webhook with Hostaway
   - `delete_webhook(account_id, webhook_id)` - Cleans up webhook on account deletion
   - Auto-provisioning after account sync completes
   - Error handling and retry logic

3. **Database Schema**
   - `hostaway.accounts` table has `webhook_id` column
   - Stores Hostaway webhook ID for cleanup on deletion

4. **Unit Tests**
   - `tests/unit/api/test_webhook.py` - Endpoint validation tests
   - `tests/unit/services/test_webhook_registration.py` - Registration service tests
   - All tests passing ✅

---

## 🔲 Remaining Work

### 1. Test Webhooks in Production

**Objective:** Verify that Hostaway is actually sending webhook events to our endpoint.

**Tasks:**
- [ ] Deploy application to staging/production environment
- [ ] Register a webhook with a real Hostaway account
- [ ] Trigger test events (create/update reservation, message, listing)
- [ ] Verify events are received at `/api/v1/hostaway/webhooks`
- [ ] Document actual payload structure from Hostaway
- [ ] Compare with Hostaway API documentation

**Acceptance Criteria:**
- Successfully receive at least one webhook event from Hostaway
- Log full payload structure for each event type
- Confirm `accountId` is present in all payloads

---

### 2. Implement Event Handlers

**Objective:** Process webhook events and update database in real-time.

**Current Code:**
```python
# sync_hostaway/routes/webhook.py (lines 80-94)
# TODO: Route to appropriate handler based on event type
if event_type.startswith("reservation."):
    handle_reservation_created(account_id, payload)
elif event_type.startswith("message."):
    logger.info("Message event received (handler not implemented yet)")
elif event_type.startswith("listing."):
    logger.info("Listing event received (handler not implemented yet)")
else:
    logger.warning(f"Unsupported event type: {event_type}")
```

**Tasks:**

#### 2a. Reservation Event Handlers
- [ ] Implement `handle_reservation_created(account_id, payload)`
  - Extract reservation data from webhook payload
  - Call `insert_reservations(engine, account_id, [data])`
  - Handle errors gracefully (don't fail webhook)
- [ ] Implement `handle_reservation_updated(account_id, payload)`
  - Same pattern as created
- [ ] Implement `handle_reservation_cancelled(account_id, payload)`
  - Update reservation status in database

#### 2b. Message Event Handlers
- [ ] Implement `handle_message_created(account_id, payload)`
  - Extract message data from webhook payload
  - Call `insert_messages(engine, account_id, [data])`
  - Handle normalization (if needed)

#### 2c. Listing Event Handlers
- [ ] Implement `handle_listing_created(account_id, payload)`
- [ ] Implement `handle_listing_updated(account_id, payload)`
- [ ] Implement `handle_listing_deleted(account_id, payload)`
  - Consider soft-delete vs hard-delete approach

**File Structure:**
```
sync_hostaway/services/
├── webhook_handlers.py (NEW)
│   ├── handle_reservation_created()
│   ├── handle_reservation_updated()
│   ├── handle_reservation_cancelled()
│   ├── handle_message_created()
│   ├── handle_listing_created()
│   ├── handle_listing_updated()
│   └── handle_listing_deleted()
```

**Design Pattern:**
```python
def handle_reservation_created(account_id: int, payload: dict[str, Any]) -> None:
    """
    Process reservation.created webhook event.

    Args:
        account_id: Hostaway account ID
        payload: Full webhook payload from Hostaway

    Raises:
        Exception: Logs error but doesn't propagate (webhook should always return 200)
    """
    try:
        # Extract reservation data from payload
        reservation_data = payload.get("data", {})

        if not reservation_data:
            logger.error("No reservation data in webhook payload", account_id=account_id)
            return

        # Use existing database writer
        from sync_hostaway.db.engine import engine
        from sync_hostaway.db.writers.reservations import insert_reservations

        insert_reservations(engine, account_id, [reservation_data])

        logger.info(
            "Webhook processed reservation.created",
            account_id=account_id,
            reservation_id=reservation_data.get("id"),
        )

    except Exception as e:
        logger.exception(
            "Error processing reservation.created webhook",
            account_id=account_id,
            error=str(e),
        )
        # Don't re-raise - webhook should return 200 even on processing errors
```

**Acceptance Criteria:**
- All event types have handlers
- Handlers reuse existing database writers (DRY principle)
- Errors are logged but don't fail webhook (always return 200)
- Handlers are covered by unit tests

---

### 3. Write Integration Tests

**Objective:** Verify end-to-end webhook processing.

**Tasks:**
- [ ] Create `tests/integration/services/test_webhook_handlers.py`
  - Test each handler inserts/updates database correctly
  - Use real database (test_engine fixture)
  - Mock nothing - test actual integration
- [ ] Create `tests/integration/api/test_webhook_e2e.py`
  - Send full webhook payloads to endpoint
  - Verify database is updated
  - Test all event types

**Example:**
```python
@pytest.mark.integration
def test_reservation_created_webhook_updates_database(test_engine):
    """Test that reservation.created webhook inserts into database."""
    # Setup: Create account
    create_account(test_engine, account_id=12345, ...)

    # Send webhook request
    payload = {
        "eventType": "reservation.created",
        "accountId": 12345,
        "data": {"id": 789, "status": "new", ...}
    }

    response = client.post("/api/v1/hostaway/webhooks", json=payload)

    # Verify: Database updated
    assert response.status_code == 200

    with test_engine.connect() as conn:
        result = conn.execute(
            select(Reservation).where(Reservation.id == 789)
        ).fetchone()
        assert result is not None
        assert result.account_id == 12345
```

---

### 4. Documentation

**Tasks:**
- [ ] Update `docs/ARCHITECTURE.md` webhook section
  - Remove "(Future)" label
  - Document actual event types supported
  - Add payload structure examples
- [ ] Add webhook guide to `docs/webhooks.md` (NEW)
  - How to register webhooks
  - Supported event types
  - Troubleshooting guide
  - Example payloads

---

## Testing Checklist

Before marking this complete:

- [ ] All unit tests pass (`pytest tests/unit/services/test_webhook_handlers.py -v`)
- [ ] All integration tests pass
- [ ] Manual testing in production shows real events being processed
- [ ] Database is correctly updated by webhook events
- [ ] No webhook events cause 500 errors
- [ ] Logging shows clear visibility into webhook processing
- [ ] Code coverage for webhook handlers ≥ 80%

---

## Success Metrics

- ✅ Webhooks registered automatically after account creation
- ✅ All Hostaway event types handled gracefully
- ✅ Database updates in real-time (< 1 second latency)
- ✅ Zero webhook failures in production (always return 200)
- ✅ Clear structured logging for debugging

---

## References

- **Hostaway Webhook Docs:** https://api.hostaway.com/docs/#/Webhooks
- **Current Implementation:** `sync_hostaway/routes/webhook.py`
- **Database Writers:** `sync_hostaway/db/writers/`
- **Tests:** `tests/unit/api/test_webhook.py`

---

## Notes

**Why This Matters:**
- Reduces polling frequency (saves API quota)
- Real-time updates for critical events (reservations, messages)
- More efficient than full syncs every N minutes

**Future Enhancements:**
- Webhook signature validation (Hostaway HMAC)
- Retry queue for failed webhook processing
- Webhook event metrics (Prometheus)
- Configurable event filtering per account
