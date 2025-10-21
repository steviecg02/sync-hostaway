# Hostaway Sync Service - Technical Requirements & Implementation Guide

**Document Version:** 2.1
**Last Updated:** 2025-10-21
**Source:** Comprehensive analysis of 4 ChatGPT conversation files (55,674 lines total)
- Chat 4: Initial architecture design (May 2025, 14,092 lines)
- Chats 1-3: Implementation conversations (July-August 2025, 41,582 lines)
**Status:** Complete technical requirements extracted from architecture and implementation conversations

## Executive Summary

The Hostaway Sync Service is a multi-tenant PMS data synchronization service that polls the Hostaway API to sync listings, reservations, and message threads into a local PostgreSQL database. The service is designed to replace direct Hostaway dependency with a local data layer that can be queried efficiently.

**Current Implementation Status:**
- **Core Architecture:** ✅ Designed and implemented
- **Database Schema:** ✅ Complete with migrations
- **Network Client:** ✅ Implemented with critical pagination fix
- **Polling Services:** 🔄 Partially implemented (~60-70%)
- **Webhook Handler:** 🔄 Partially implemented (~25-50%)
- **Testing Coverage:** ❌ Not started
- **Production Hardening:** 🔄 Deferred recommendations documented

**Key Technical Achievements:**
- Multi-tenant architecture with account_id and customer_id columns
- Smart retry logic for API failures (429, timeout, 5xx)
- Pagination bug fixed (offset vs page parameter)
- Database upsert pattern with IS DISTINCT FROM optimization
- Token refresh logic with 403 handling
- Docker Compose setup with tmpfs for local development

**Remaining High-Priority Work:**
1. Complete webhook implementation and testing
2. Implement comprehensive test coverage (unit + integration)
3. Background job verification with real account lifecycle
4. Production hardening (Gunicorn, logging, error handling)
5. Infrastructure improvements (monitoring, health checks)

---

## Table of Contents

1. [Initial Architecture Design (May 2025)](#initial-architecture-design-may-2025)
2. [Architecture Overview](#architecture-overview)
3. [Database Schema](#database-schema)
4. [Network Client Implementation](#network-client-implementation)
5. [Polling Services](#polling-services)
6. [Webhook Implementation](#webhook-implementation)
7. [Testing Requirements](#testing-requirements)
8. [Production Requirements](#production-requirements)
9. [Infrastructure & Deployment](#infrastructure--deployment)
10. [TODO List with Priorities](#todo-list-with-priorities)
11. [Technical Decisions & Rationale](#technical-decisions--rationale)
12. [Side Recommendations](#side-recommendations)
13. [Next Steps](#next-steps)

---

## Initial Architecture Design (May 2025)

**Source:** Chat 4 - "sync-hostaway" (14,092 lines, May 14-16, 2025)

This section documents the foundational architecture decisions made during the initial design phase, before implementation began in July 2025. Understanding these original decisions provides critical context for why the system is structured the way it is.

### Multi-PMS Sync Architecture (Core Design Principle)

**Original Vision:** Build a platform that can sync data from ANY property management system (PMS), not just Hostaway.

**Architecture Pattern:**
- **Each PMS gets its own dedicated sync service**
  - `sync-hostaway` for Hostaway
  - `sync-guesty` for Guesty (future)
  - `sync-hospitable` for Hospitable (future)

- **Each service stores raw PMS data AS-IS**
  - No normalization at sync time
  - PMS-specific schemas in PostgreSQL (e.g., `hostaway`, `guesty`)
  - Preserves complete API payloads for future flexibility

- **Separate normalization service handles cross-PMS data**
  - Future `core` schema for normalized multi-PMS views
  - ETL jobs transform PMS-specific data → normalized abstractions
  - Enables queries across multiple PMS providers

**Why This Matters:**
- Explains why the service stores raw JSON payloads instead of normalized columns
- Explains the `hostaway` schema naming (prepares for `guesty`, etc.)
- Explains why the service is called `sync-hostaway`, not just `hostaway-sync`

**Quote from Initial Design:**
> "We want to build a system that works with multiple PMS providers. Each PMS sync service stores raw data in its own schema. A separate normalization layer will handle cross-PMS queries."

---

### Raw Data Storage vs Normalization Separation

**Design Decision:** Sync services are NOT responsible for data normalization.

**Responsibilities of sync-hostaway:**
1. Poll Hostaway API endpoints
2. Store raw JSON payloads in `hostaway` schema
3. Maintain sync state (last sync time, errors, etc.)
4. Handle API authentication and rate limiting

**Responsibilities of future normalization service:**
1. Read from `hostaway.listings`, `guesty.listings`, etc.
2. Transform to common schema in `core.properties`
3. Handle PMS-specific quirks and field mappings
4. Provide multi-PMS query interface

**Current Implementation Status:**
- ✅ Raw storage in `hostaway` schema implemented
- ❌ Normalization service not yet built
- ❌ `core` schema defined but not used

**Evidence:**
> "Don't normalize at sync time. Just store the raw payload. We'll build a separate service to normalize across multiple PMS providers later."

---

### Schema-per-Microservice Pattern

**PostgreSQL Schema Design:**
```sql
-- PMS-specific schemas (raw data)
CREATE SCHEMA IF NOT EXISTS hostaway;
CREATE SCHEMA IF NOT EXISTS guesty;
CREATE SCHEMA IF NOT EXISTS hospitable;

-- Normalized multi-PMS schema (future)
CREATE SCHEMA IF NOT EXISTS core;
```

**Pattern:**
- Each sync service owns its schema
- Schema name matches PMS provider
- Alembic migrations are schema-aware
- Services cannot write to other schemas

**Alembic Configuration:**
```python
# env.py
def run_migrations_online():
    # Explicitly create schema before running migrations
    with connectable.connect() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS hostaway"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS core"))

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="hostaway"  # Schema-specific version table
        )
```

**Migration Template:**
```python
def upgrade():
    # Always specify schema in operations
    op.create_table(
        'listings',
        sa.Column('id', sa.Integer(), nullable=False),
        ...,
        schema='hostaway'  # Explicit schema
    )
```

---

### Module Structure & Contract Design

**Original Module Layout:**
```
sync_hostaway/
├── hostaway_api/       # Network/HTTP boundary (fetch from Hostaway API)
├── normalizers/        # Raw → structured transformations
├── db/
│   └── writers/        # Persistence layer (insert into PostgreSQL)
├── pollers/            # Orchestration (schedule polling jobs)
└── config.py           # Centralized configuration
```

**Contract Violations Discovered During Initial Design:**

**Problem 1: Normalizers importing from db/writers**
- **Violation:** normalizers/ should transform data, not persist it
- **Fix:** Move all database logic to db/writers, normalizers return dicts

**Problem 2: Pollers directly importing insert functions**
- **Violation:** Pollers should orchestrate, not handle persistence details
- **Fix:** Pollers call db/writers functions, don't implement insert logic

**Problem 3: Multiple config patterns**
- **Violation:** Some modules used DEBUG flag, others used LOG_LEVEL
- **Fix:** Single LOG_LEVEL in config.py, remove DEBUG flags

**Final Simplified Structure:**
```
sync_hostaway/
├── client.py           # Network client (fetch_page, fetch_paginated)
├── insert.py           # Database writers (insert_listings, etc.)
├── poller.py           # Polling orchestration
├── webhook.py          # Webhook handlers
├── models.py           # SQLAlchemy ORM models
├── config.py           # Centralized configuration
└── main.py             # FastAPI app
```

**Why The Simplification:**
- Original structure over-engineered for single PMS
- Contracts weren't adding value at current scale
- Easier to test with flatter structure
- Can re-introduce layers when multi-PMS support is added

---

### Phase-Based Authentication Strategy

**Phase 1: Hardwired .env Tokens (Current Implementation)**
- `HOSTAWAY_ACCOUNT_ID` - Hardcoded account ID
- `HOSTAWAY_CLIENT_SECRET` - Hardcoded client secret
- `HOSTAWAY_ACCESS_TOKEN` - Hardcoded access token
- Single-tenant operation
- Good for MVP and testing

**Phase 2: Database-Backed Credentials (Future)**
- `hostaway.accounts` table stores per-account credentials
- `account_id`, `client_secret`, `access_token` columns
- Multi-tenant support
- POST /accounts endpoint to add new accounts
- Webhook authentication per-account (webhook_login, webhook_password)

**Current Status:**
- ✅ Phase 1 environment variable pattern implemented
- ✅ Phase 2 accounts table schema exists
- 🔄 Migration path from Phase 1 → Phase 2 not documented

**Migration Strategy (When Ready for Phase 2):**
```python
# 1. Keep .env vars as fallback
# 2. Check database first, fall back to .env
# 3. Gradually migrate accounts to database
# 4. Remove .env fallback once all accounts migrated

def get_account_credentials(account_id: Optional[int] = None):
    if account_id:
        # Phase 2: Fetch from database
        return fetch_from_accounts_table(account_id)
    else:
        # Phase 1: Use environment variables
        return {
            "account_id": os.getenv("HOSTAWAY_ACCOUNT_ID"),
            "client_secret": os.getenv("HOSTAWAY_CLIENT_SECRET"),
            "access_token": os.getenv("HOSTAWAY_ACCESS_TOKEN"),
        }
```

---

### SQLAlchemy Core vs ORM Decision

**Initial Debate:** Use SQLAlchemy Core (Table objects) or ORM (declarative classes)?

**Decision:** Use ORM (declarative classes)

**Rationale:**
- Better type hints and IDE support
- Easier relationship definitions (for future foreign keys)
- More readable model definitions
- Still can drop to Core for complex queries

**Pattern:**
```python
# ORM declarative model
class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"schema": "hostaway"}

    id = Column(Integer, primary_key=True, autoincrement=False)
    account_id = Column(Integer, ForeignKey("hostaway.accounts.account_id"), nullable=False)
    raw_payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# But use Core for bulk inserts
stmt = insert(Listing).values(rows)
stmt = stmt.on_conflict_do_update(...)
```

**Hybrid Approach:**
- Define models with ORM for schema clarity
- Use Core insert() for performance-critical bulk operations
- Use ORM sessions for simple CRUD operations

---

### Message Thread Storage Design

**Original Question:** How to store message threads?

**Options Considered:**
1. One row per message (normalized)
2. One row per reservation with JSON array of messages (denormalized)
3. Separate messages table with foreign key to reservations

**Decision:** Option 2 - One row per reservation with JSON array

**Schema:**
```sql
CREATE TABLE hostaway.messages (
    reservation_id INTEGER PRIMARY KEY,  -- 1:1 with reservations
    account_id INTEGER NOT NULL,
    customer_id UUID,
    raw_messages JSONB NOT NULL,  -- Array of message objects
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Rationale:**
- Messages are always queried per-reservation (never individually)
- Hostaway API returns messages per-reservation (natural API boundary)
- JSON array preserves chronological order
- Simpler upsert logic (one row = one conversation)
- JSONB allows indexing/querying individual messages if needed

**Storage Pattern:**
```python
# Fetch messages for reservation
messages = fetch_paginated(f"reservations/{reservation_id}/messages", token)

# Sort by timestamp (oldest first)
sorted_messages = sorted(messages, key=lambda m: m.get("createdAt", ""))

# Store entire thread as JSON array
insert_messages(engine, account_id, {
    reservation_id: sorted_messages
})
```

**Query Pattern:**
```sql
-- Get all messages for a reservation
SELECT raw_messages FROM hostaway.messages WHERE reservation_id = 12345;

-- Search within messages using JSONB operators
SELECT * FROM hostaway.messages
WHERE raw_messages @> '[{"type": "automated"}]';
```

---

### Testing Strategy: Write Tests After Each Task

**Original Instruction:**
> "Write tests after you complete each task. Don't wait until the end of the project. This prevents testing debt."

**Pattern:**
- Complete feature (e.g., fetch_listings)
- Write unit tests for that feature
- Mark task complete only when tests pass
- Move to next feature

**Test Markers:**
```python
@pytest.mark.unit           # Fast, isolated, mocked dependencies
@pytest.mark.integration    # Real DB, real API (use with care)
@pytest.mark.functional     # End-to-end scenarios
```

**Test File Structure:**
```
tests/
├── unit/
│   ├── test_client.py       # Tests for client.py
│   ├── test_insert.py       # Tests for insert.py
│   ├── test_poller.py       # Tests for poller.py
│   └── test_webhook.py      # Tests for webhook.py
└── integration/
    ├── test_poll_cycle.py   # Full poll → insert → verify
    └── test_webhook_e2e.py  # Webhook → insert → verify
```

**Current Status:**
- ❌ Testing strategy defined but not followed during implementation
- ❌ No unit tests written yet (technical debt)
- ❌ No integration tests written yet

**Lesson Learned:**
ChatGPT did not follow this instruction. Tests were deferred to "later" repeatedly, creating significant technical debt.

---

### Configuration Management: Single Source of Truth

**Design Principle:** All configuration in `config.py`, loaded from environment variables.

**Pattern:**
```python
# config.py
import os

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/sync_hostaway")

# Hostaway API
BASE_URL = os.getenv("HOSTAWAY_API_BASE_URL", "https://api.hostaway.com/v1/")
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "0.67"))  # 1.5 req/sec
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "4"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # Single log level, not DEBUG flag

# Phase 1: Hardwired credentials
HOSTAWAY_ACCOUNT_ID = int(os.getenv("HOSTAWAY_ACCOUNT_ID", "0"))
HOSTAWAY_CLIENT_SECRET = os.getenv("HOSTAWAY_CLIENT_SECRET", "")
HOSTAWAY_ACCESS_TOKEN = os.getenv("HOSTAWAY_ACCESS_TOKEN", "")
```

**Import Pattern:**
```python
# Other modules import from config
from sync_hostaway.config import DATABASE_URL, LOG_LEVEL, MAX_RETRIES
```

**Anti-Pattern (Avoided):**
```python
# DON'T do this - scatter config across modules
DEBUG = os.getenv("DEBUG", "false") == "true"
DB_URL = os.getenv("DB_URL")  # Inconsistent naming
```

**Validation (Not Implemented Yet):**
```python
# Should validate on startup
required_vars = ["DATABASE_URL", "HOSTAWAY_CLIENT_SECRET"]
missing = [v for v in required_vars if not globals()[v]]
if missing:
    raise RuntimeError(f"Missing required config: {missing}")
```

---

### Alembic Setup with Schema Management

**Initial Setup Pattern:**

**alembic.ini:**
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://localhost/sync_hostaway
version_table_schema = hostaway  # Store migration versions in hostaway schema
```

**env.py:**
```python
from sync_hostaway.models import Base

def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))

    with connectable.connect() as connection:
        # Create schemas before running migrations
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS hostaway"))
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS core"))

        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            version_table_schema="hostaway",
            include_schemas=True,
        )

        with context.begin_transaction():
            context.run_migrations()
```

**Migration Template (script.py.mako):**
```python
def upgrade():
    ${upgrades if upgrades else "pass"}

def downgrade():
    ${downgrades if downgrades else "pass"}
```

**First Migration (001_initial_schema.py):**
```python
def upgrade():
    # Schemas already created by env.py

    # Create accounts table
    op.create_table(
        'accounts',
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=True),
        sa.Column('client_secret', sa.String(), nullable=False),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('webhook_login', sa.String(), nullable=True),
        sa.Column('webhook_password', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('account_id'),
        schema='hostaway'
    )

    # Create indexes
    op.create_index('idx_accounts_customer_id', 'accounts', ['customer_id'], schema='hostaway')

    # Create listings table
    # ... (similar pattern)
```

**Key Patterns:**
1. Always specify `schema='hostaway'` in operations
2. Migrations create schemas before tables
3. Version table stored in `hostaway` schema (not public)
4. Indexes explicitly specify schema

---

### Upsert Logic with IS DISTINCT FROM

**Original Discussion:** How to handle duplicate syncs without unnecessary writes?

**Problem:**
- Polling runs every 15 minutes
- Most listings/reservations haven't changed
- Naive upsert writes every time → unnecessary I/O and updated_at changes

**Solution:** Use `IS DISTINCT FROM` in ON CONFLICT WHERE clause.

**Pattern:**
```python
stmt = insert(Listing).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=["id"],
    set_={
        "raw_payload": insert(Listing).excluded.raw_payload,
        "updated_at": insert(Listing).excluded.updated_at,
    },
    where=(
        Listing.raw_payload.is_distinct_from(insert(Listing).excluded.raw_payload)
    ),
)
```

**SQL Translation:**
```sql
INSERT INTO hostaway.listings (id, account_id, raw_payload, ...)
VALUES (...)
ON CONFLICT (id) DO UPDATE SET
    raw_payload = EXCLUDED.raw_payload,
    updated_at = EXCLUDED.updated_at
WHERE listings.raw_payload IS DISTINCT FROM EXCLUDED.raw_payload;
```

**Behavior:**
- If raw_payload hasn't changed → WHERE clause false → no update
- If raw_payload has changed → WHERE clause true → update executes
- `updated_at` only changes when data actually changes

**Performance Impact:**
- Reduces write I/O by ~95% after initial sync
- Prevents index bloat from unnecessary updates
- Makes `updated_at` timestamp meaningful (actual changes, not just syncs)

---

### Evolution from Initial Design to Final Implementation

**What Changed from May → July/August:**

1. **Module Structure Simplified**
   - Removed hostaway_api/, normalizers/, db/writers/ structure
   - Flattened to client.py, insert.py, poller.py
   - Rationale: Over-engineered for single-PMS MVP

2. **listing_id Removed from Messages Table**
   - Initial design had listing_id in messages
   - Discovered reservations can move between listings
   - Changed to reservation_id as primary key (1:1 relationship)

3. **account_id Made Explicit Parameter**
   - Initial design extracted from payload
   - Discovered payload doesn't reliably contain accountId
   - Changed to explicit parameter passed by caller

4. **Pagination Bug Fixed**
   - Initial design used `page` parameter
   - Discovered Hostaway API uses `offset`, not `page`
   - Fixed to calculate offset = page_number * limit

5. **Testing Strategy Not Followed**
   - Initial design called for tests after each task
   - ChatGPT deferred tests repeatedly
   - Now have technical debt of ~0% test coverage

**What Stayed the Same:**

1. ✅ Raw data storage in `hostaway` schema
2. ✅ Multi-PMS architecture vision (even if not implemented yet)
3. ✅ Schema-per-microservice pattern
4. ✅ Message thread storage as JSON array per reservation
5. ✅ IS DISTINCT FROM upsert optimization
6. ✅ Phase 1/Phase 2 authentication strategy
7. ✅ Alembic schema-aware migrations

---

### Key Takeaways from Initial Design

**Architectural Principles That Guided Implementation:**
1. **Separation of concerns:** Sync ≠ normalization
2. **Future-proofing:** Design for multi-PMS even if building single-PMS first
3. **Raw data preservation:** Store complete payloads, normalize later
4. **Schema isolation:** Each service owns its schema
5. **Testing discipline:** Write tests after each task (even if not followed)

**Decisions That Prevented Future Pain:**
- Raw JSON storage (flexibility to change normalization logic)
- Schema-per-service (easy to add new PMS providers)
- Phase-based auth (smooth migration from single → multi-tenant)
- IS DISTINCT FROM (prevents write amplification)

**Decisions That Were Corrected During Implementation:**
- Over-engineered module structure → simplified
- listing_id in messages → removed (data model issue)
- Extracting account_id from payload → explicit parameter
- Using `page` parameter → using `offset`

**Technical Debt Created:**
- Testing strategy defined but not executed
- Normalization service designed but not built
- `core` schema exists but unused
- Token cache service discussed but deferred

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Hostaway Sync Service                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Polling    │  │   Webhook    │  │   Account    │     │
│  │   Services   │  │   Handler    │  │   Manager    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                           │                                  │
│                    ┌──────▼──────┐                          │
│                    │   Network   │                          │
│                    │   Client    │                          │
│                    └──────┬──────┘                          │
│                           │                                  │
│                    ┌──────▼──────┐                          │
│                    │  Database   │                          │
│                    │   Layer     │                          │
│                    └─────────────┘                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │   PostgreSQL  │
                   │ (2 schemas)   │
                   └───────────────┘
```

### Multi-Tenancy Strategy

**Two-Tier Tenant Identification:**
- `account_id`: Hostaway account ID (from Hostaway API)
- `customer_id`: Internal customer UUID (for future multi-customer support)

**Design Decision:** Every table includes both columns for future flexibility, even though initial implementation uses only account_id.

### Data Flow Patterns

1. **Polling Flow:**
   - Background jobs poll Hostaway API on schedule
   - fetch_paginated retrieves all pages for an endpoint
   - Data normalized and inserted via insert_* functions
   - ON CONFLICT DO UPDATE with IS DISTINCT FROM prevents unnecessary writes

2. **Webhook Flow:**
   - Hostaway sends webhook events to POST /webhooks/hostaway
   - Event routed by eventType (listing.created, reservation.updated, etc.)
   - Raw payload normalized and inserted/updated
   - Deduplication mechanism prevents duplicate processing

3. **Account Management Flow:**
   - POST /accounts creates new account and triggers background sync
   - GET /accounts/{account_id} retrieves account status
   - DELETE /accounts/{account_id} removes account and cascades to data

---

## Database Schema

### Schema Design

**Two Separate Schemas:**
- `hostaway` schema: PMS-specific data (listings, reservations, messages)
- `core` schema: Multi-PMS abstractions (future)

**Status:** Using `hostaway` schema exclusively for initial implementation.

### Table Definitions

#### `hostaway.accounts`

```sql
CREATE TABLE hostaway.accounts (
    account_id INTEGER PRIMARY KEY,
    customer_id UUID,
    client_secret VARCHAR NOT NULL,
    access_token VARCHAR NOT NULL,
    webhook_login VARCHAR,
    webhook_password VARCHAR,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_accounts_customer_id ON hostaway.accounts(customer_id);
```

**SQLAlchemy Model:**
```python
class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "hostaway"}

    account_id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(UUID, nullable=True, index=True)
    client_secret = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    webhook_login = Column(String, nullable=True)
    webhook_password = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
```

#### `hostaway.listings`

```sql
CREATE TABLE hostaway.listings (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES hostaway.accounts(account_id) ON DELETE CASCADE,
    customer_id UUID,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_listings_account_id ON hostaway.listings(account_id);
CREATE INDEX idx_listings_customer_id ON hostaway.listings(customer_id);
```

**SQLAlchemy Model:**
```python
class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = {"schema": "hostaway"}

    id = Column(Integer, primary_key=True, autoincrement=False)
    account_id = Column(Integer, ForeignKey("hostaway.accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(UUID, nullable=True, index=True)
    raw_payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

#### `hostaway.reservations`

```sql
CREATE TABLE hostaway.reservations (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES hostaway.accounts(account_id) ON DELETE CASCADE,
    customer_id UUID,
    listing_id INTEGER NOT NULL,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reservations_account_id ON hostaway.reservations(account_id);
CREATE INDEX idx_reservations_customer_id ON hostaway.reservations(customer_id);
CREATE INDEX idx_reservations_listing_id ON hostaway.reservations(listing_id);
```

**SQLAlchemy Model:**
```python
class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = {"schema": "hostaway"}

    id = Column(Integer, primary_key=True, autoincrement=False)
    account_id = Column(Integer, ForeignKey("hostaway.accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(UUID, nullable=True, index=True)
    listing_id = Column(Integer, nullable=False, index=True)
    raw_payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

#### `hostaway.messages`

**Design Decision:** No listing_id column because reservations can move between listings.

```sql
CREATE TABLE hostaway.messages (
    reservation_id INTEGER PRIMARY KEY REFERENCES hostaway.reservations(id) ON DELETE CASCADE,
    account_id INTEGER NOT NULL REFERENCES hostaway.accounts(account_id) ON DELETE CASCADE,
    customer_id UUID,
    raw_messages JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_account_id ON hostaway.messages(account_id);
CREATE INDEX idx_messages_customer_id ON hostaway.messages(customer_id);
```

**SQLAlchemy Model:**
```python
class MessageThread(Base):
    """
    One message thread per reservation.
    No listing_id because reservations can move between listings.
    reservation_id serves as primary key (enforces 1:1 relationship).
    """
    __tablename__ = "messages"
    __table_args__ = {"schema": "hostaway"}

    reservation_id = Column(Integer, ForeignKey("hostaway.reservations.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    account_id = Column(Integer, ForeignKey("hostaway.accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(UUID, nullable=True, index=True)
    raw_messages = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Schema Migrations

**Tool:** Alembic

**Migration Commands:**
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Show current version
alembic current

# Show migration history
alembic history
```

**Key Migration Patterns:**

1. **Creating schemas:**
```python
op.execute("CREATE SCHEMA IF NOT EXISTS hostaway")
op.execute("CREATE SCHEMA IF NOT EXISTS core")
```

2. **Schema-qualified table creation:**
```python
op.create_table(
    'accounts',
    sa.Column('account_id', sa.Integer(), nullable=False),
    ...,
    schema='hostaway'
)
```

3. **Adding indexes:**
```python
op.create_index(
    'idx_listings_account_id',
    'listings',
    ['account_id'],
    schema='hostaway'
)
```

### Critical Schema Changes Made During Implementation

**Change 1: Remove listing_id from messages table**
- **Reason:** Reservations can move between listings (guest rebooks, host changes assignment)
- **Impact:** Messages table now has 1:1 relationship with reservations (reservation_id is PK)
- **Migration Pattern:**
```python
# Remove column
op.drop_column('messages', 'listing_id', schema='hostaway')

# Change primary key
op.drop_constraint('messages_pkey', 'messages', schema='hostaway')
op.create_primary_key('messages_pkey', 'messages', ['reservation_id'], schema='hostaway')
```

**Change 2: Add account_id parameter to all insert functions**
- **Reason:** Payload doesn't reliably contain accountId, causing NULL constraint violations
- **Pattern:** Pass account_id explicitly from caller who knows the context
```python
# Before (broken)
def insert_listings(engine: Engine, data: list[dict], dry_run: bool = False):
    account_id = listing.get("accountId")  # Returns None!

# After (correct)
def insert_listings(engine: Engine, account_id: int, data: list[dict], dry_run: bool = False):
    rows.append({"account_id": account_id, ...})  # Use parameter
```

---

## Network Client Implementation

### Core Functions

#### `fetch_page()` - Single Page Fetch with Retry Logic

**Location:** `sync_hostaway/client.py`

**Signature:**
```python
def fetch_page(
    endpoint: str,
    token: str,
    page_number: int = 0,
    offset: Optional[int] = None,
    limit: Optional[int] = 100,
    account_id: Optional[int] = None,
) -> Tuple[Dict[str, Any], int]:
```

**Critical Implementation Details:**

1. **Pagination Uses Offset, NOT Page Parameter**
   - **Bug Fixed:** Initial implementation used `params = {"page": page_number}` which caused duplicate results
   - **Correct Pattern:**
   ```python
   params = {
       "limit": limit or 100,
       "offset": offset if offset is not None else page_number * (limit or 100)
   }
   ```

2. **Smart Retry Logic**
   - Only retry on: 429 (rate limit), timeout, or 5xx errors
   - **Do NOT retry** on 4xx errors (except 403 for token refresh)
   - MAX_RETRIES = 2 (bounded attempts)

3. **Token Refresh on 403**
   ```python
   if res.status_code == 403 and account_id is not None:
       logger.warning("403 Unauthorized; refreshing token")
       token = get_or_refresh_token(account_id, prev_token=token, prev_status=403)
       headers["Authorization"] = f"Bearer {token}"
       retries += 1
       if retries > MAX_RETRIES:
           res.raise_for_status()
       continue
   ```

4. **Rate Limit Handling**
   ```python
   if res.status_code == 429:
       logger.warning("Rate limited. Sleeping %.1fs", REQUEST_DELAY * 2)
       time.sleep(REQUEST_DELAY * 2)
       retries += 1
       if retries > MAX_RETRIES:
           res.raise_for_status()
       continue
   ```

**Full Implementation:**
```python
def fetch_page(
    endpoint: str,
    token: str,
    page_number: int = 0,
    offset: Optional[int] = None,
    limit: Optional[int] = 100,
    account_id: Optional[int] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Fetch a single page of results from a Hostaway API endpoint.

    Args:
        endpoint (str): The Hostaway API endpoint (e.g. 'reservations').
        token (str): Bearer token for Hostaway authentication.
        page_number (int, optional): Page number for offset calculation. Defaults to 0.
        offset (Optional[int], optional): Explicit offset override. Defaults to None.
        limit (Optional[int], optional): Max records per page. Defaults to 100.
        account_id (Optional[int], optional): Hostaway account ID (used for token refresh). Defaults to None.

    Returns:
        Tuple[Dict[str, Any], int]: A tuple of the JSON response and HTTP status code.

    Raises:
        requests.RequestException: If request fails after retries.
    """
    url = urljoin(BASE_URL, endpoint)
    headers = {"Authorization": f"Bearer {token}"}
    page_limit = limit or 100
    params = {
        "limit": page_limit,
        "offset": offset if offset is not None else page_number * page_limit,
    }

    retries = 0
    while True:
        try:
            logger.debug("Requesting %s offset=%s", endpoint, params["offset"])
            res = requests.get(url, headers=headers, params=params, timeout=5)

            # Token refresh on 403
            if res.status_code == 403 and account_id is not None:
                logger.warning("403 Unauthorized on %s offset=%s; refreshing token", endpoint, params["offset"])
                token = get_or_refresh_token(account_id, prev_token=token, prev_status=403)
                headers["Authorization"] = f"Bearer {token}"
                retries += 1
                if retries > MAX_RETRIES:
                    res.raise_for_status()
                continue

            # Rate limit handling
            if res.status_code == 429:
                logger.warning("Rate limited on offset=%s. Sleeping %.1fs", params["offset"], REQUEST_DELAY * 2)
                time.sleep(REQUEST_DELAY * 2)
                retries += 1
                if retries > MAX_RETRIES:
                    res.raise_for_status()
                continue

            res.raise_for_status()
            return cast(Dict[str, Any], res.json()), res.status_code

        except requests.RequestException as err:
            logger.warning("Error fetching %s offset=%s: %s", endpoint, params["offset"], str(err))
            retries += 1
            if retries > MAX_RETRIES or not should_retry(res if "res" in locals() else None, err):
                raise
            time.sleep(REQUEST_DELAY * retries)
```

#### `fetch_paginated()` - Multi-Page Concurrent Fetch

**Location:** `sync_hostaway/client.py`

**Signature:**
```python
def fetch_paginated(
    endpoint: str,
    token: str,
    limit: int = 100,
    account_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
```

**Implementation Pattern:**

1. **Fetch First Page to Determine Total**
   ```python
   first_page, _ = fetch_page(endpoint, token, page_number=0, limit=limit, account_id=account_id)
   total_count = first_page.get("count", 0)
   results = first_page.get("result", [])
   ```

2. **Calculate Remaining Pages**
   ```python
   if total_count > limit:
       num_pages = (total_count + limit - 1) // limit
       remaining_pages = range(1, num_pages)
   ```

3. **Concurrent Fetch with ThreadPoolExecutor**
   ```python
   with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
       futures = {
           executor.submit(fetch_page, endpoint, token, page_num, None, limit, account_id): page_num
           for page_num in remaining_pages
       }
       for future in as_completed(futures):
           page_data, _ = future.result()
           results.extend(page_data.get("result", []))
   ```

4. **Fail-Fast Error Handling**
   - Any page failure raises exception immediately
   - No partial results returned on error

**Configuration Constants:**
```python
BASE_URL = "https://api.hostaway.com/v1/"
REQUEST_DELAY = 1.0 / 1.5  # Rate limit: 1.5 req/sec
MAX_RETRIES = 2
MAX_CONCURRENT_REQUESTS = 4
```

#### `get_or_refresh_token()` - Token Management

**Purpose:** Refresh access token when expired (403) or proactively fetch from cache.

**Signature:**
```python
def get_or_refresh_token(
    account_id: int,
    prev_token: Optional[str] = None,
    prev_status: Optional[int] = None,
) -> str:
```

**Implementation Status:** Basic pattern implemented, full token cache service deferred.

**Current Pattern:**
```python
def get_or_refresh_token(account_id: int, prev_token: Optional[str] = None, prev_status: Optional[int] = None) -> str:
    """
    Retrieve or refresh the access token for a Hostaway account.

    Args:
        account_id: Hostaway account ID
        prev_token: Previous token that failed (if any)
        prev_status: HTTP status that triggered refresh (if any)

    Returns:
        str: Valid access token
    """
    # TODO: Implement token cache service
    # For now, fetch from database
    with engine.begin() as conn:
        result = conn.execute(
            select(Account.access_token, Account.client_secret)
            .where(Account.account_id == account_id)
        ).fetchone()

        if not result:
            raise ValueError(f"Account {account_id} not found")

        access_token, client_secret = result

        # If previous token failed with 403, refresh it
        if prev_status == 403:
            # Call Hostaway token refresh endpoint
            # Update database with new token
            pass

        return access_token
```

### Database Insert Functions

**Pattern:** All insert functions accept explicit `account_id` parameter (not extracted from payload).

#### `insert_listings()`

```python
def insert_listings(
    engine: Engine,
    account_id: int,
    data: list[dict[str, Any]],
    dry_run: bool = False
) -> None:
    """
    Upsert listings into the database — only update if raw_payload has changed.

    Args:
        engine: SQLAlchemy engine
        account_id: Hostaway account ID (explicit parameter)
        data: List of listing dictionaries from Hostaway API
        dry_run: If True, log operations without executing
    """
    now = datetime.now(tz=timezone.utc)

    rows = []
    for listing in data:
        listing_id = listing.get("id")

        if not listing_id:
            logger.warning("Skipping listing with missing id")
            continue

        rows.append({
            "id": listing_id,
            "account_id": account_id,  # Use parameter, not payload
            "customer_id": None,
            "raw_payload": listing,
            "created_at": now,
            "updated_at": now,
        })

    if not rows:
        return

    if dry_run:
        logger.info("DRY RUN: Would insert/update %d listings", len(rows))
        return

    with engine.begin() as conn:
        stmt = insert(Listing).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "raw_payload": insert(Listing).excluded.raw_payload,
                "updated_at": insert(Listing).excluded.updated_at,
            },
            where=Listing.raw_payload.is_distinct_from(
                insert(Listing).excluded.raw_payload
            ),
        )
        conn.execute(stmt)
        logger.info("Inserted/updated %d listings", len(rows))
```

#### `insert_reservations()`

```python
def insert_reservations(
    engine: Engine,
    account_id: int,
    data: list[dict[str, Any]],
    dry_run: bool = False
) -> None:
    """
    Upsert reservations into the database — only update if raw_payload has changed.

    Args:
        engine: SQLAlchemy engine
        account_id: Hostaway account ID (explicit parameter)
        data: List of reservation dictionaries from Hostaway API
        dry_run: If True, log operations without executing
    """
    now = datetime.now(tz=timezone.utc)

    rows = []
    for r in data:
        reservation_id = r.get("id")
        listing_id = r.get("listingMapId")

        if not reservation_id or not listing_id:
            logger.warning("Skipping reservation with missing id or listingMapId")
            continue

        rows.append({
            "id": reservation_id,
            "account_id": account_id,  # Use parameter, not payload
            "customer_id": None,
            "listing_id": listing_id,
            "raw_payload": r,
            "created_at": now,
            "updated_at": now,
        })

    if not rows:
        return

    if dry_run:
        logger.info("DRY RUN: Would insert/update %d reservations", len(rows))
        return

    with engine.begin() as conn:
        stmt = insert(Reservation).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "raw_payload": insert(Reservation).excluded.raw_payload,
                "listing_id": insert(Reservation).excluded.listing_id,
                "updated_at": insert(Reservation).excluded.updated_at,
            },
            where=Reservation.raw_payload.is_distinct_from(
                insert(Reservation).excluded.raw_payload
            ),
        )
        conn.execute(stmt)
        logger.info("Inserted/updated %d reservations", len(rows))
```

#### `insert_messages()`

```python
def insert_messages(
    engine: Engine,
    account_id: int,
    data: dict[int, list[dict[str, Any]]],
    dry_run: bool = False
) -> None:
    """
    Upsert message threads into the database — only update if raw_messages has changed.

    Args:
        engine: SQLAlchemy engine
        account_id: Hostaway account ID (explicit parameter)
        data: Dictionary mapping reservation_id -> list of messages
        dry_run: If True, log operations without executing
    """
    now = datetime.now(tz=timezone.utc)

    rows = []
    for reservation_id, messages in data.items():
        if not reservation_id:
            logger.warning("Skipping message thread with missing reservation_id")
            continue

        rows.append({
            "reservation_id": reservation_id,
            "account_id": account_id,  # Use parameter, not payload
            "customer_id": None,
            "raw_messages": messages,
            "created_at": now,
            "updated_at": now,
        })

    if not rows:
        return

    if dry_run:
        logger.info("DRY RUN: Would insert/update %d message threads", len(rows))
        return

    with engine.begin() as conn:
        stmt = insert(MessageThread).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["reservation_id"],
            set_={
                "raw_messages": insert(MessageThread).excluded.raw_messages,
                "updated_at": insert(MessageThread).excluded.updated_at,
            },
            where=MessageThread.raw_messages.is_distinct_from(
                insert(MessageThread).excluded.raw_messages
            ),
        )
        conn.execute(stmt)
        logger.info("Inserted/updated %d message threads", len(rows))
```

**Critical Pattern:** `IS DISTINCT FROM` in ON CONFLICT prevents unnecessary updates when payload hasn't changed.

---

## Polling Services

### Poll Functions

**Location:** `sync_hostaway/poller.py`

#### `poll_listings()`

```python
def poll_listings(account_id: int, engine: Engine, dry_run: bool = False) -> None:
    """
    Poll all listings for a Hostaway account and insert into database.

    Args:
        account_id: Hostaway account ID
        engine: SQLAlchemy engine
        dry_run: If True, log operations without executing
    """
    token = get_or_refresh_token(account_id)
    listings = fetch_paginated("listings", token, limit=100, account_id=account_id)
    logger.info("Fetched %d listings for account %d", len(listings), account_id)
    insert_listings(engine, account_id, listings, dry_run=dry_run)
```

#### `poll_reservations()`

```python
def poll_reservations(account_id: int, engine: Engine, dry_run: bool = False) -> None:
    """
    Poll all reservations for a Hostaway account and insert into database.

    Args:
        account_id: Hostaway account ID
        engine: SQLAlchemy engine
        dry_run: If True, log operations without executing
    """
    token = get_or_refresh_token(account_id)
    reservations = fetch_paginated("reservations", token, limit=100, account_id=account_id)
    logger.info("Fetched %d reservations for account %d", len(reservations), account_id)
    insert_reservations(engine, account_id, reservations, dry_run=dry_run)
```

#### `poll_messages()`

**Note:** Messages endpoint requires reservation_id, so must poll per-reservation.

```python
def poll_messages(account_id: int, engine: Engine, dry_run: bool = False) -> None:
    """
    Poll message threads for all reservations and insert into database.

    Args:
        account_id: Hostaway account ID
        engine: SQLAlchemy engine
        dry_run: If True, log operations without executing
    """
    token = get_or_refresh_token(account_id)

    # Fetch all reservation IDs first
    with engine.connect() as conn:
        result = conn.execute(
            select(Reservation.id)
            .where(Reservation.account_id == account_id)
        )
        reservation_ids = [row[0] for row in result]

    logger.info("Polling messages for %d reservations", len(reservation_ids))

    message_data = {}
    for reservation_id in reservation_ids:
        try:
            messages = fetch_paginated(
                f"reservations/{reservation_id}/messages",
                token,
                limit=100,
                account_id=account_id
            )
            if messages:
                message_data[reservation_id] = messages
        except Exception as e:
            logger.warning("Failed to fetch messages for reservation %d: %s", reservation_id, str(e))
            continue

    insert_messages(engine, account_id, message_data, dry_run=dry_run)
```

### Background Job Scheduling

**Status:** Partially implemented, needs verification.

**Implementation Pattern:**
- FastAPI lifespan event spawns background tasks
- Each poll function runs on schedule (e.g., every 15 minutes)
- Uses asyncio.create_task() for non-blocking execution

**Example:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: spawn background jobs
    for account_id in get_active_account_ids():
        asyncio.create_task(poll_account_loop(account_id))

    yield

    # Shutdown: cleanup
```

**TODO:** Verify background jobs trigger correctly when account is added via POST /accounts.

---

## Webhook Implementation

### Webhook Endpoint

**Route:** `POST /webhooks/hostaway`

**Authentication:** Basic auth using webhook_login and webhook_password from accounts table.

**Implementation Status:** ~25-50% complete

### Event Types

**Supported Events:**
- `listing.created`
- `listing.updated`
- `listing.deleted`
- `reservation.created`
- `reservation.updated`
- `reservation.cancelled`
- `message.created`

**Event Routing Pattern:**
```python
@app.post("/webhooks/hostaway")
async def handle_webhook(request: Request):
    """
    Handle incoming Hostaway webhook events.

    Authenticates using Basic Auth (webhook_login/webhook_password).
    Routes events by eventType to appropriate handler.
    """
    # Authenticate
    auth = request.headers.get("Authorization")
    if not auth or not validate_webhook_auth(auth):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Parse payload
    payload = await request.json()
    event_type = payload.get("eventType")
    account_id = payload.get("accountId")

    # Route to handler
    if event_type == "listing.created":
        handle_listing_created(account_id, payload)
    elif event_type == "listing.updated":
        handle_listing_updated(account_id, payload)
    # ... etc

    return {"status": "ok"}
```

### Event Handlers (Partial Implementation)

**Pattern:** Extract relevant data from webhook payload, normalize, and call insert function.

```python
def handle_listing_created(account_id: int, payload: dict) -> None:
    """Handle listing.created webhook event."""
    listing_data = payload.get("data", {})
    insert_listings(engine, account_id, [listing_data], dry_run=False)

def handle_reservation_updated(account_id: int, payload: dict) -> None:
    """Handle reservation.updated webhook event."""
    reservation_data = payload.get("data", {})
    insert_reservations(engine, account_id, [reservation_data], dry_run=False)
```

### Deduplication Mechanism

**Problem:** Webhooks can arrive multiple times for same event.

**Solution:** Use updated_at timestamp and IS DISTINCT FROM to prevent duplicate writes.

**Status:** Deduplication logic built into insert functions (ON CONFLICT DO UPDATE with IS DISTINCT FROM).

### Webhook Testing

**TODO:**
- Unit tests for webhook route handler
- Unit tests for event parser and router
- Integration test with mock Hostaway webhook payloads
- Test authentication failure cases
- Test malformed payload handling

---

## Testing Requirements

### Testing Strategy

**Approach:** Bottom-up testing (unit → integration → functional)

**Framework:** pytest with markers

**Test Markers:**
```python
@pytest.mark.unit       # Fast, isolated, mocked
@pytest.mark.integration  # Real DB, real API (with care)
@pytest.mark.functional   # End-to-end scenarios
```

### Unit Tests (Not Started)

**Priority:** HIGH

**Test Files Needed:**
- `tests/unit/test_client.py` - Network client functions
- `tests/unit/test_insert.py` - Database insert functions
- `tests/unit/test_poller.py` - Polling logic
- `tests/unit/test_webhook.py` - Webhook handlers

**Test Cases Required:**

#### `test_client.py`

```python
@pytest.mark.unit
def test_fetch_page_success():
    """Test fetch_page returns data correctly."""
    pass

@pytest.mark.unit
def test_fetch_page_retries_on_429():
    """Test fetch_page retries on rate limit."""
    pass

@pytest.mark.unit
def test_fetch_page_refreshes_token_on_403():
    """Test fetch_page calls get_or_refresh_token on 403."""
    pass

@pytest.mark.unit
def test_fetch_page_fails_fast_on_404():
    """Test fetch_page does not retry on 404."""
    pass

@pytest.mark.unit
def test_fetch_paginated_handles_multiple_pages():
    """Test fetch_paginated fetches all pages correctly."""
    pass

@pytest.mark.unit
def test_fetch_paginated_uses_offset_not_page():
    """Test fetch_paginated uses offset parameter (regression test)."""
    pass
```

#### `test_insert.py`

```python
@pytest.mark.unit
def test_insert_listings_creates_new_records():
    """Test insert_listings creates new listings."""
    pass

@pytest.mark.unit
def test_insert_listings_updates_changed_payload():
    """Test insert_listings updates when payload changes."""
    pass

@pytest.mark.unit
def test_insert_listings_skips_unchanged_payload():
    """Test insert_listings skips update when payload unchanged (IS DISTINCT FROM)."""
    pass

@pytest.mark.unit
def test_insert_listings_uses_explicit_account_id():
    """Test insert_listings uses account_id parameter, not payload (regression test)."""
    pass

@pytest.mark.unit
def test_insert_reservations_creates_new_records():
    """Test insert_reservations creates new reservations."""
    pass

@pytest.mark.unit
def test_insert_messages_uses_reservation_id_as_pk():
    """Test insert_messages enforces 1:1 relationship with reservations."""
    pass

@pytest.mark.unit
def test_insert_dry_run_does_not_write():
    """Test dry_run=True logs operations without writing to DB."""
    pass
```

#### `test_webhook.py`

```python
@pytest.mark.unit
def test_webhook_authenticates_basic_auth():
    """Test webhook endpoint validates Basic Auth credentials."""
    pass

@pytest.mark.unit
def test_webhook_routes_listing_created():
    """Test webhook routes listing.created to correct handler."""
    pass

@pytest.mark.unit
def test_webhook_routes_reservation_updated():
    """Test webhook routes reservation.updated to correct handler."""
    pass

@pytest.mark.unit
def test_webhook_handles_malformed_payload():
    """Test webhook returns 400 on malformed JSON."""
    pass
```

### Integration Tests (Deferred)

**Priority:** MEDIUM

**Reason for Deferral:** Wait until schema stabilizes and core unit tests pass.

**Test Cases Needed:**
- Full poll-and-insert cycle with real DB
- Webhook end-to-end with real DB
- Token refresh with real Hostaway API (use test account)
- Multi-tenant data isolation verification

### Test Configuration

**conftest.py Pattern:**
```python
import pytest
from sqlalchemy import create_engine
from sync_hostaway.config import DATABASE_URL

@pytest.fixture(scope="session")
def engine():
    """Create test database engine."""
    return create_engine(DATABASE_URL)

@pytest.fixture(scope="function")
def db_session(engine):
    """Create isolated database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()

    yield connection

    transaction.rollback()
    connection.close()

@pytest.fixture
def mock_hostaway_api():
    """Mock Hostaway API responses for unit tests."""
    # Return mock requests.Response objects
    pass
```

**Running Tests:**
```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run with coverage
pytest --cov=sync_hostaway

# Run specific test file
pytest tests/unit/test_client.py

# Run specific test
pytest tests/unit/test_client.py::test_fetch_page_retries_on_429
```

---

## Production Requirements

### Production Hardening Checklist

**Status:** Many items deferred, documented here for implementation.

#### 1. Error Handling & Logging

- [ ] **Structured logging format** (JSON logs for aggregation)
  ```python
  import structlog
  logger = structlog.get_logger()
  logger.info("poll_completed", account_id=123, records=456, duration_ms=789)
  ```

- [ ] **Error boundary pattern** - Catch exceptions at service boundaries
  ```python
  try:
      poll_listings(account_id, engine)
  except Exception as e:
      logger.error("poll_failed", account_id=account_id, error=str(e), exc_info=True)
      # Send alert, don't crash service
  ```

- [ ] **Request ID tracing** - Propagate request ID through all log entries

- [ ] **Log rotation and retention** - Use logrotate or similar

#### 2. Configuration Management

- [ ] **Validate all environment variables on startup**
  ```python
  required_vars = ["DATABASE_URL", "HOSTAWAY_API_KEY", ...]
  missing = [v for v in required_vars if not os.getenv(v)]
  if missing:
      raise RuntimeError(f"Missing required env vars: {missing}")
  ```

- [ ] **Fallback values for optional config** with warnings
  ```python
  MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
  if "MAX_RETRIES" not in os.environ:
      logger.warning("MAX_RETRIES not set, using default: 2")
  ```

- [ ] **Config validation tests** (ensure .env.example matches actual requirements)

#### 3. Database Connection Management

- [ ] **Connection pooling configuration**
  ```python
  engine = create_engine(
      DATABASE_URL,
      pool_size=10,
      max_overflow=20,
      pool_pre_ping=True,  # Verify connections before use
      pool_recycle=3600,   # Recycle connections every hour
  )
  ```

- [ ] **Connection health checks** in readiness probe

- [ ] **Graceful degradation** if database is temporarily unavailable

#### 4. API Rate Limiting & Backoff

- [ ] **Exponential backoff** for retries (currently linear)
  ```python
  time.sleep(REQUEST_DELAY * (2 ** retries))
  ```

- [ ] **Jitter in backoff** to prevent thundering herd
  ```python
  import random
  time.sleep((REQUEST_DELAY * (2 ** retries)) * (0.5 + random.random()))
  ```

- [ ] **Circuit breaker pattern** for failing endpoints

#### 5. Monitoring & Observability

- [ ] **Health check endpoint** (`GET /health`)
  ```python
  @app.get("/health")
  async def health():
      return {"status": "ok", "version": __version__}
  ```

- [ ] **Readiness check endpoint** (`GET /ready`)
  ```python
  @app.get("/ready")
  async def ready():
      # Check database connection
      # Check background jobs running
      return {"status": "ready"}
  ```

- [ ] **Metrics endpoint** (`GET /metrics`) for Prometheus
  - Polling success/failure counts
  - API request latency histograms
  - Database query durations
  - Active account count

- [ ] **Sentry or similar for error tracking**

- [ ] **Datadog or similar for APM**

#### 6. Security

- [ ] **Secrets management** - Use Vault, AWS Secrets Manager, or similar (not .env files)

- [ ] **API token encryption at rest** - Encrypt access_token column in database

- [ ] **Webhook payload validation** - Verify signatures if Hostaway provides them

- [ ] **Rate limiting on webhook endpoint** - Prevent abuse

- [ ] **Input validation** - Validate all user inputs with Pydantic models

#### 7. Deployment & Operations

- [ ] **Docker image optimization** - Multi-stage build, minimal base image

- [ ] **Graceful shutdown** - Handle SIGTERM properly
  ```python
  import signal

  def shutdown_handler(signum, frame):
      logger.info("Shutdown signal received, draining connections...")
      # Cancel background tasks
      # Close database connections
      sys.exit(0)

  signal.signal(signal.SIGTERM, shutdown_handler)
  ```

- [ ] **Rolling deployments** - Zero-downtime deployment strategy

- [ ] **Database migration strategy** - Run migrations before deployment or as init container

- [ ] **Rollback plan** - Document how to rollback failed deployment

#### 8. Performance

- [ ] **Database query optimization** - Add indexes for common queries

- [ ] **Connection reuse** - Reuse HTTP connections with requests.Session

- [ ] **Batch processing** - Process webhook events in batches if high volume

- [ ] **Query result caching** - Cache frequently accessed data (e.g., account configs)

#### 9. Testing in Production

- [ ] **Feature flags** - Toggle new features without deployment

- [ ] **Canary deployments** - Test changes on subset of traffic

- [ ] **Shadow testing** - Run new code alongside old code, compare results

### Production Server Configuration

**Recommended:** Gunicorn with Uvicorn workers

**Configuration:**
```bash
# Number of workers = (2 × CPU cores) + 1
gunicorn sync_hostaway.main:app \
    --workers 5 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --graceful-timeout 30 \
    --log-level info \
    --access-logfile - \
    --error-logfile -
```

**Docker Entrypoint:**
```dockerfile
CMD ["gunicorn", "sync_hostaway.main:app", "--workers", "5", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

**CPU Core Detection:**
```python
import os
num_cpus = os.cpu_count()
logger.info("Detected %d CPU cores", num_cpus)
num_workers = (2 * num_cpus) + 1
logger.info("Recommended workers: %d", num_workers)
```

---

## Infrastructure & Deployment

### Docker Compose Setup

**Status:** ✅ Implemented for local development

**docker-compose.yml:**
```yaml
version: "3.8"

services:
  db:
    image: postgres:15
    container_name: sync_hostaway_db
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_USER: postgres
      POSTGRES_DB: sync_hostaway
    ports:
      - "5432:5432"
    tmpfs:
      - /var/lib/postgresql/data  # No persistence for local dev
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - sync_network

  sync_hostaway:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: sync_hostaway
    command: uvicorn sync_hostaway.main:app --host 0.0.0.0 --port 8000 --reload
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/sync_hostaway
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - .:/app  # Mount source for hot reload
    networks:
      - sync_network

networks:
  sync_network:
    driver: bridge
```

**Usage:**
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f sync_hostaway

# Stop services (data is lost due to tmpfs)
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

### Dockerfile

**Multi-stage build pattern:**
```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY sync_hostaway/ /app/sync_hostaway/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/

# Ensure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn sync_hostaway.main:app --host 0.0.0.0 --port 8000"]
```

### Environment Variables

**Required:**
```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Hostaway API
HOSTAWAY_API_BASE_URL=https://api.hostaway.com/v1/

# Service Configuration
MAX_RETRIES=2
MAX_CONCURRENT_REQUESTS=4
REQUEST_DELAY=0.67  # 1.5 req/sec
DEBUG=false

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json  # json or text
```

**Optional:**
```bash
# Sentry (error tracking)
SENTRY_DSN=https://...

# Datadog (APM)
DD_AGENT_HOST=localhost
DD_TRACE_ENABLED=true
```

### Database Initialization

**First-time setup:**
```bash
# Run migrations
docker-compose exec sync_hostaway alembic upgrade head

# Verify tables created
docker-compose exec db psql -U postgres -d sync_hostaway -c "\dt hostaway.*"
```

**Reset database (local dev only):**
```bash
docker-compose down
docker-compose up -d  # tmpfs ensures clean state
docker-compose exec sync_hostaway alembic upgrade head
```

### Production Deployment

**Kubernetes Example (Partial):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sync-hostaway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sync-hostaway
  template:
    metadata:
      labels:
        app: sync-hostaway
    spec:
      initContainers:
      - name: migrate
        image: sync-hostaway:latest
        command: ["alembic", "upgrade", "head"]
        envFrom:
        - secretRef:
            name: sync-hostaway-secrets

      containers:
      - name: sync-hostaway
        image: sync-hostaway:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: sync-hostaway-secrets
        - configMapRef:
            name: sync-hostaway-config

        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10

        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5

        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

---

## TODO List with Priorities

### P0 - Critical (Blocking MVP)

- [ ] **Complete webhook implementation**
  - [ ] Implement all event handlers (listing, reservation, message)
  - [ ] Add Basic Auth validation
  - [ ] Test with mock Hostaway webhook payloads
  - [ ] Verify deduplication works correctly

- [ ] **Implement core unit tests**
  - [ ] `test_client.py` - All fetch functions
  - [ ] `test_insert.py` - All database insert functions
  - [ ] `test_webhook.py` - Webhook routing and handlers
  - [ ] Achieve >80% code coverage on core functions

- [ ] **Background job verification**
  - [ ] Delete test accounts from database
  - [ ] Re-add via POST /accounts endpoint
  - [ ] Confirm background polling jobs trigger automatically
  - [ ] Verify data appears in listings, reservations, messages tables

- [ ] **Fix token refresh logic**
  - [ ] Implement full get_or_refresh_token() function
  - [ ] Call Hostaway token refresh endpoint on 403
  - [ ] Update database with new token
  - [ ] Test with expired token scenario

### P1 - High Priority (MVP Quality)

- [ ] **Error handling improvements**
  - [ ] Add try-catch at all service boundaries
  - [ ] Implement error logging with context
  - [ ] Add request ID tracing
  - [ ] Test failure scenarios (DB down, API down, etc.)

- [ ] **Configuration validation**
  - [ ] Validate all required env vars on startup
  - [ ] Add warnings for missing optional vars with defaults
  - [ ] Create .env.example with all vars documented
  - [ ] Test with missing required vars (should fail fast)

- [ ] **Health checks**
  - [ ] Implement GET /health endpoint
  - [ ] Implement GET /ready endpoint (check DB connection)
  - [ ] Test health checks in Docker Compose
  - [ ] Add health check to Dockerfile

- [ ] **Logging improvements**
  - [ ] Add structured logging (JSON format)
  - [ ] Log all API requests with latency
  - [ ] Log all database operations with duration
  - [ ] Configure log levels properly (DEBUG for dev, INFO for prod)

### P2 - Medium Priority (Production Ready)

- [ ] **Integration tests**
  - [ ] Full poll-and-insert cycle test with real DB
  - [ ] Webhook end-to-end test with real DB
  - [ ] Multi-tenant data isolation test
  - [ ] Token refresh integration test (with test Hostaway account)

- [ ] **Production server configuration**
  - [ ] Set up Gunicorn with Uvicorn workers
  - [ ] Calculate optimal worker count based on CPU cores
  - [ ] Configure timeouts and graceful shutdown
  - [ ] Test under load

- [ ] **Database optimizations**
  - [ ] Add indexes for common query patterns
  - [ ] Configure connection pooling (pool_size, max_overflow)
  - [ ] Test connection pool under load
  - [ ] Add pool_pre_ping for connection health

- [ ] **Monitoring & metrics**
  - [ ] Implement GET /metrics endpoint (Prometheus format)
  - [ ] Add polling success/failure counters
  - [ ] Add API latency histograms
  - [ ] Add database query duration tracking

- [ ] **Security hardening**
  - [ ] Encrypt access_token column in database
  - [ ] Implement webhook payload signature validation
  - [ ] Add rate limiting on webhook endpoint
  - [ ] Use secrets manager (not .env) for production

### P3 - Low Priority (Nice to Have)

- [ ] **Token cache service**
  - [ ] Implement in-memory token cache (Redis or similar)
  - [ ] Proactively refresh tokens before expiration
  - [ ] Reduce database queries for token lookup

- [ ] **Batch webhook processing**
  - [ ] Queue webhook events if high volume
  - [ ] Process in batches to reduce database round-trips
  - [ ] Add queue monitoring metrics

- [ ] **Circuit breaker pattern**
  - [ ] Implement for Hostaway API calls
  - [ ] Auto-disable polling if API consistently fails
  - [ ] Auto-enable after cooldown period

- [ ] **Query result caching**
  - [ ] Cache account configurations
  - [ ] Cache frequently accessed reservation/listing data
  - [ ] Invalidate cache on webhook updates

- [ ] **Feature flags**
  - [ ] Add feature flag system (LaunchDarkly or similar)
  - [ ] Flag new webhook event types
  - [ ] Flag experimental optimizations

- [ ] **Canary deployments**
  - [ ] Set up deployment pipeline for canary releases
  - [ ] Route 10% of traffic to new version
  - [ ] Auto-rollback on error rate increase

### Deferred (Future Considerations)

- [ ] **Multi-PMS support**
  - [ ] Abstract PMS-specific logic to adapters
  - [ ] Create `core` schema for normalized multi-PMS data
  - [ ] Implement Guesty adapter
  - [ ] Implement Hospitable adapter

- [ ] **Advanced polling strategies**
  - [ ] Polling window staggering for multi-tenant (avoid thundering herd)
  - [ ] Adaptive polling frequency based on activity
  - [ ] Incremental polling (only fetch changed records)

- [ ] **Data retention policies**
  - [ ] Archive old reservations after checkout + N days
  - [ ] Compress historical message threads
  - [ ] Implement data export for compliance

- [ ] **Advanced observability**
  - [ ] Distributed tracing with OpenTelemetry
  - [ ] Custom dashboards in Grafana
  - [ ] Alerting rules for critical failures

---

## Technical Decisions & Rationale

### 1. Why No listing_id in messages Table?

**Problem:** Initial schema had listing_id in messages table.

**Issue:** Reservations can move between listings:
- Guest cancels and rebooks at different property
- Host reassigns reservation to different unit
- Reservation mobility breaks listing_id relationship

**Solution:** Use reservation_id as primary key (1:1 relationship).

**Evidence:** User feedback: "Reservations can move between listings, so you can't rely on listing_id."

**Migration:**
```python
# Remove listing_id column
op.drop_column('messages', 'listing_id', schema='hostaway')

# Change primary key to reservation_id
op.drop_constraint('messages_pkey', 'messages', schema='hostaway')
op.create_primary_key('messages_pkey', 'messages', ['reservation_id'], schema='hostaway')
```

---

### 2. Why Explicit account_id Parameter Instead of Extracting from Payload?

**Problem:** Initial implementation extracted account_id from payload with `r.get("accountId")`.

**Issue:** Payload doesn't reliably contain accountId → NULL values → constraint violations → all records appear as duplicates.

**Solution:** Pass account_id as explicit parameter from caller who knows the context.

**Evidence:** User feedback: "I updated the inserts to accept account_id. it wasnt in the payload like you said it would be"

**Pattern:**
```python
# Caller knows account_id
def poll_listings(account_id: int, engine: Engine):
    listings = fetch_paginated("listings", token, account_id=account_id)
    insert_listings(engine, account_id, listings)  # Pass explicitly

# Insert function uses parameter
def insert_listings(engine: Engine, account_id: int, data: list):
    rows.append({"account_id": account_id, ...})  # Use param, not payload
```

---

### 3. Why offset Parameter Instead of page?

**Problem:** Initial `fetch_page()` used `params = {"page": page_number}`.

**Issue:** Hostaway API uses **offset**, not page → all requests hit offset=0 → duplicates.

**Evidence:** Logs showed 800 total reservations = 100 unique × 8 duplicate pages.

**Solution:** Change params to use offset.

**Before (broken):**
```python
params = {"limit": 100, "page": page_number}
```

**After (correct):**
```python
params = {
    "limit": limit or 100,
    "offset": offset if offset is not None else page_number * (limit or 100)
}
```

---

### 4. Why IS DISTINCT FROM in ON CONFLICT DO UPDATE?

**Problem:** Without IS DISTINCT FROM, every upsert writes to database even if payload hasn't changed.

**Impact:** Unnecessary writes, updated_at timestamp changes without real updates, database bloat.

**Solution:** Use IS DISTINCT FROM in WHERE clause of upsert.

**Pattern:**
```python
stmt = stmt.on_conflict_do_update(
    index_elements=["id"],
    set_={
        "raw_payload": insert(Listing).excluded.raw_payload,
        "updated_at": insert(Listing).excluded.updated_at,
    },
    where=Listing.raw_payload.is_distinct_from(
        insert(Listing).excluded.raw_payload
    ),
)
```

**Result:** Update only executes if raw_payload actually changed.

---

### 5. Why Smart Retry Logic (Only 429, Timeout, 5xx)?

**Problem:** Naive retry on all errors wastes time and resources.

**Pattern:**
- **Do retry:** 429 (rate limit), timeout, 5xx (server error) → Transient, may succeed on retry
- **Don't retry:** 4xx (except 403 for token refresh) → Client error, retry won't help

**Implementation:**
```python
def should_retry(response: Optional[requests.Response], exception: Exception) -> bool:
    """Determine if request should be retried."""
    if isinstance(exception, requests.Timeout):
        return True

    if response is None:
        return False

    # Retry on 429 or 5xx
    if response.status_code == 429 or response.status_code >= 500:
        return True

    return False
```

---

### 6. Why MAX_RETRIES = 2?

**Problem:** Unbounded retries can cause infinite loops or excessive API calls.

**Solution:** Limit retries to 2 attempts (3 total tries including initial request).

**Rationale:**
- Most transient failures resolve within 1-2 retries
- Prevents runaway retry loops
- Fails fast on persistent errors

---

### 7. Why ThreadPoolExecutor for Pagination?

**Problem:** Sequential page fetching is slow (100 pages × 1 second = 100 seconds).

**Solution:** Concurrent page fetching with ThreadPoolExecutor.

**Configuration:**
```python
MAX_CONCURRENT_REQUESTS = 4  # Balance between speed and rate limits
```

**Pattern:**
```python
with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
    futures = {executor.submit(fetch_page, ...): page_num for page_num in pages}
    for future in as_completed(futures):
        results.extend(future.result())
```

**Result:** 100 pages fetched in ~25 seconds instead of 100 seconds.

---

### 8. Why Separate hostaway and core Schemas?

**Problem:** Future multi-PMS support requires PMS-agnostic abstractions.

**Solution:** Two schemas:
- `hostaway` - PMS-specific raw data
- `core` - Normalized multi-PMS data (future)

**Current Status:** Only using `hostaway` schema for initial implementation.

**Future Pattern:**
- Raw data stored in `hostaway.listings`, `guesty.listings`, etc.
- Normalized data in `core.properties` (multi-PMS view)
- ETL jobs transform PMS-specific → core abstractions

---

### 9. Why tmpfs for Local Database?

**Problem:** Local development database persists data between restarts → schema changes break → manual cleanup needed.

**Solution:** Use tmpfs in Docker Compose → data lost on container restart → clean slate every time.

**Configuration:**
```yaml
db:
  tmpfs:
    - /var/lib/postgresql/data
```

**Result:** `docker-compose down && docker-compose up` gives clean database every time.

---

### 10. Why Defer DB Integration Tests?

**Problem:** Schema still evolving, tests would break with every migration.

**Decision:** Defer integration tests until schema stabilizes.

**Rationale:**
- Unit tests provide coverage for logic
- Integration tests require stable contracts
- Schema changes invalidate integration test fixtures

**Timeline:** Implement integration tests after P0 work complete.

---

## Side Recommendations

These are recommendations made during implementation that were deferred or documented for later consideration.

### 1. Gunicorn with Uvicorn Workers

**Why:** Production-grade ASGI server with process management.

**Configuration:**
```bash
gunicorn sync_hostaway.main:app \
    --workers $((2 * $(nproc) + 1)) \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120
```

**Benefits:**
- Multiple worker processes for parallelism
- Automatic worker restart on failure
- Graceful shutdown handling
- Better resource utilization

---

### 2. CPU Core Logging for Runtime Validation

**Why:** Validate deployment configuration matches hardware.

**Pattern:**
```python
import os
num_cpus = os.cpu_count()
logger.info("Detected %d CPU cores", num_cpus)
num_workers = (2 * num_cpus) + 1
logger.info("Recommended workers: %d", num_workers)
```

**Use Case:** Verify Kubernetes resource requests match container limits.

---

### 3. .env Fallback Behavior Improvements

**Current:** Silent fallback to None if env var missing.

**Improvement:** Log warning when using default value.

```python
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
if "MAX_RETRIES" not in os.environ:
    logger.warning("MAX_RETRIES not set in environment, using default: 2")
```

**Benefit:** Catch misconfiguration early.

---

### 4. Token Cache Service (Future)

**Why:** Reduce database queries for token lookup.

**Pattern:**
- Redis cache: `account:{account_id}:token`
- TTL based on token expiration
- Proactive refresh before expiration

**Implementation:**
```python
def get_or_refresh_token(account_id: int) -> str:
    # Check cache first
    cached = redis.get(f"account:{account_id}:token")
    if cached:
        return cached

    # Fetch from database
    token = fetch_token_from_db(account_id)

    # Cache with TTL
    redis.setex(f"account:{account_id}:token", 3600, token)

    return token
```

---

### 5. Structured Logging Format

**Why:** Enable log aggregation and querying.

**Implementation:**
```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()
logger.info("poll_completed", account_id=123, records=456, duration_ms=789)
```

**Output:**
```json
{"event": "poll_completed", "account_id": 123, "records": 456, "duration_ms": 789, "timestamp": "2024-01-15T10:30:45Z", "level": "info"}
```

---

### 6. Pre-Fetch Normalization Layer

**Why:** Standardize payload structure before database insert.

**Pattern:**
```python
def normalize_listing(raw: dict) -> dict:
    """Normalize Hostaway listing payload to standard format."""
    return {
        "id": raw["id"],
        "name": raw.get("name", ""),
        "address": extract_address(raw),
        "bedrooms": raw.get("bedrooms", 0),
        # ...
    }

def insert_listings(engine, account_id, data):
    normalized = [normalize_listing(r) for r in data]
    # Insert normalized data
```

**Benefits:**
- Isolate payload structure changes
- Easier testing (test normalization separately)
- Cleaner insert logic

---

### 7. Process Titles for Debugging

**Why:** Identify workers in `ps` output.

**Implementation:**
```python
import setproctitle

def poll_account_loop(account_id: int):
    setproctitle.setproctitle(f"sync_hostaway: poller account_id={account_id}")
    while True:
        poll_listings(account_id, engine)
        time.sleep(900)
```

**Result:** `ps aux` shows `sync_hostaway: poller account_id=123` instead of generic `python`.

---

### 8. Polling Window Staggering for Multi-Tenant

**Problem:** All accounts poll at same time → thundering herd on API.

**Solution:** Stagger polling start times.

**Pattern:**
```python
import random

async def start_polling_jobs():
    accounts = get_all_accounts()
    for i, account in enumerate(accounts):
        # Stagger by 1 minute per account
        delay = i * 60
        asyncio.create_task(poll_with_delay(account.account_id, delay))

async def poll_with_delay(account_id: int, delay: int):
    await asyncio.sleep(delay)
    while True:
        poll_all_endpoints(account_id)
        await asyncio.sleep(900)  # 15 minutes
```

---

## Next Steps

### Immediate Actions (This Week)

1. **Complete webhook implementation** (P0)
   - Implement all event handlers
   - Add Basic Auth validation
   - Write unit tests
   - Test with mock payloads

2. **Implement core unit tests** (P0)
   - `test_client.py` - Focus on pagination and retry logic
   - `test_insert.py` - Focus on upsert logic and IS DISTINCT FROM
   - `test_webhook.py` - Focus on routing and auth
   - Aim for >80% coverage

3. **Verify background job lifecycle** (P0)
   - Delete test accounts
   - Re-add via API
   - Confirm polling triggers
   - Verify data syncs correctly

4. **Fix token refresh logic** (P0)
   - Implement full get_or_refresh_token()
   - Call Hostaway refresh endpoint
   - Test with expired token

### Short-Term (Next 2 Weeks)

1. **Error handling & logging** (P1)
   - Add try-catch at service boundaries
   - Implement structured logging (JSON)
   - Add request ID tracing

2. **Health checks** (P1)
   - Implement /health and /ready endpoints
   - Add to Docker Compose
   - Test in deployment

3. **Configuration validation** (P1)
   - Validate env vars on startup
   - Create .env.example
   - Add warnings for defaults

### Medium-Term (Next Month)

1. **Integration tests** (P2)
   - Full poll-and-insert cycle
   - Webhook end-to-end
   - Multi-tenant isolation

2. **Production server setup** (P2)
   - Configure Gunicorn with Uvicorn workers
   - Optimize worker count
   - Test under load

3. **Monitoring & metrics** (P2)
   - Implement /metrics endpoint
   - Add key metrics (polling success, latency, etc.)
   - Set up Prometheus/Grafana

### Long-Term (Next Quarter)

1. **Security hardening** (P2)
   - Encrypt tokens at rest
   - Webhook signature validation
   - Secrets manager integration

2. **Advanced features** (P3)
   - Token cache service
   - Circuit breaker pattern
   - Feature flags

3. **Multi-PMS preparation** (Deferred)
   - Design core schema
   - Abstract PMS-specific logic
   - Implement first adapter (Guesty or Hospitable)

---

## Appendix: Key Files & Locations

### Source Code Structure

```
sync_hostaway/
├── __init__.py
├── main.py                 # FastAPI app, routes, lifespan
├── config.py               # Environment variables, DATABASE_URL
├── models.py               # SQLAlchemy ORM models
├── client.py               # fetch_page, fetch_paginated, get_or_refresh_token
├── insert.py               # insert_listings, insert_reservations, insert_messages
├── poller.py               # poll_listings, poll_reservations, poll_messages
├── webhook.py              # Webhook route handler and event parsers
└── utils.py                # Helper functions

alembic/
├── env.py                  # Alembic environment configuration
├── script.py.mako          # Migration template
└── versions/               # Migration files
    ├── 001_initial_schema.py
    ├── 002_remove_listing_id_from_messages.py
    └── ...

tests/
├── conftest.py             # Pytest fixtures
├── unit/
│   ├── test_client.py
│   ├── test_insert.py
│   ├── test_poller.py
│   └── test_webhook.py
└── integration/
    ├── test_poll_cycle.py
    └── test_webhook_e2e.py

docker-compose.yml          # Local development environment
Dockerfile                  # Production image
requirements.txt            # Python dependencies
alembic.ini                 # Alembic configuration
.env.example                # Example environment variables
```

### Critical Files to Review

1. **`sync_hostaway/client.py`** - Contains pagination bug fix (offset vs page)
2. **`sync_hostaway/insert.py`** - Contains account_id parameter pattern
3. **`sync_hostaway/models.py`** - Contains final schema definitions
4. **`alembic/versions/002_*.py`** - Contains listing_id removal migration
5. **`docker-compose.yml`** - Contains tmpfs configuration

---

## Document Maintenance

**When to Update This Document:**
- After implementing P0 tasks (update status, add learnings)
- After major schema changes (update models, migration patterns)
- After discovering new bugs (add to decisions section)
- After production deployment (add deployment notes, lessons learned)

**Document Owner:** Stephen Guilfoil

**Last Review:** 2025-10-21

---

**END OF DOCUMENT**
