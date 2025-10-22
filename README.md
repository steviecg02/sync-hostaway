# Sync Hostaway

A production-grade Hostaway data sync agent that:

- Ingests listings, reservations, and messages from Hostaway's PMS API
- Normalizes and writes data to PostgreSQL (with Alembic migrations)
- Listens for Hostaway webhooks and syncs deltas in near real-time
- Structured and modular codebase with service-layer orchestration
- Fully typed with logging, configuration, and test scaffolding

## Features

- ⏳ Syncs Hostaway data into normalized tables (`listings`, `reservations`, `messages`)
- 📤 Listens to webhook pushes for near real-time updates
- 🔄 Skips unchanged data with `IS DISTINCT FROM` upserts
- 🔧 Modular: `pollers/`, `normalizers/`, `writers/`, `services/`
- 🧪 Testable: Pytest scaffolding, with CLI and DB isolation
- 📦 Docker-ready with `Makefile` automation and `.env` config

## Project Structure

```
sync-hostaway/
├── alembic/                 # Migrations
├── sync_hostaway/
│   ├── db/writers/          # Engine & Output logic (DB)
│   ├── hostaway_api/        # Authentication and Client
│   ├── models/              # SQLAlchemy Core table definitions
│   ├── normalizers/         # Data shaping per entity
│   ├── pollers/             # API polling logic (listings, reservations, messages)
│   ├── services/            # Orchestration logic (sync runner)
│   ├── config.py            # Loads DB config from env
│   └── ...
├── tests/                   # Pytest suite
├── Dockerfile               # Multi-stage container
├── Makefile                 # CLI automation
└── README.md
```

## Quick Start

### Local Development Setup

**1. Clone and install dependencies:**

```bash
git clone <repo-url>
cd sync-hostaway

# Create virtual environment and install dependencies
make venv
source venv/bin/activate
make install-dev
```

**2. Create `.env` file:**

```bash
# Database (connects to Docker Postgres)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres

# API Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Logging
LOG_LEVEL=INFO

# Development
DRY_RUN=false
```

**3. Start PostgreSQL in Docker:**

```bash
docker-compose up -d postgres
```

**4. Run database migrations:**

```bash
alembic upgrade head
```

**5. Run the API locally:**

```bash
uvicorn sync_hostaway.main:app --reload
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

---

## Development Workflow

### Running Locally (Recommended for Development)

**Database in Docker, API running locally:**

```bash
# Terminal 1: Start database
docker-compose up postgres

# Terminal 2: Run API with hot reload
source venv/bin/activate
uvicorn sync_hostaway.main:app --reload --host 0.0.0.0 --port 8000
```

**Benefits:**
- Fast reload on code changes
- Easy debugging with breakpoints
- Direct access to logs

### Running Everything in Docker

**Full stack (database + API) in Docker:**

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop everything
docker-compose down
```

**Note:** Migrations run automatically via `entrypoint.sh` when the app container starts.

---

## Testing

```bash
# Run all tests
make test

# Run specific test file
pytest tests/unit/test_client.py -v

# Run with coverage
make test  # Generates htmlcov/index.html
```

## Code Quality

```bash
# Format code
make format

# Run linters
make lint

# Type check
mypy sync_hostaway/
```

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Add new field"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

---

## 📌 Tasks

### ✅ Task 1: Normalize + Sync Core Entities
- [x] Normalize listings, reservations, messages
- [x] Use `ON CONFLICT DO UPDATE` with `IS DISTINCT FROM`
- [x] Store full PMS payload in `pms_meta`
- [x] Modularize pollers, normalizers, inserts
- [x] Log/skip rows with FK issues
- [ ] 🔴 Write tests for all existing functionality

---

### 🔄 Task 2: Webhook Receiver + Initial API Layer

#### 2a. Webhook Receiver
- [ ] FastAPI route `/webhook/hostaway`
- [ ] Parse incoming `eventType`, dispatch to pollers
- [ ] Schedule once-daily pull (hardcoded credentials for now)
- [ ] Stub out automation dispatcher interface

#### 2b. Public API Endpoints
- [ ] `/calendar/{listing_id}` → availability
- [ ] `/reservations/{reservation_id}` → reservation details
- [ ] Protect endpoints (will be scoped per-host in Task 5)

---

### 🧾 Task 3: Hostaway Account Registry + Token Configuration

- [ ] Create `hostaway_accounts` table:
  - `id`, `client_id`, `client_secret`, `access_token`
  - `is_active`, `created_at`, `updated_at`
- [ ] POST `/accounts`:
  - Accepts `client_id`, `client_secret`
  - Calls Hostaway auth endpoint to **obtain access_token**
  - Stores all credentials securely (see Task 5)
  - Triggers **initial full sync**
- [ ] PATCH `/accounts/{id}`:
  - Disable or rotate credentials

---

### 🧠 Task 4: Multi-Account Daemon Pulls

- [ ] Daemon process to sync **all active accounts**
- [ ] Pull runs daily, scoped to account tokens
- [ ] Future: `last_synced_at` tracking per entity
- [ ] Isolate + log errors by account
- [ ] Trigger retry logic for failed accounts (future)

---

### 🔐 Task 5: Security, Credential Storage & Access Control

- [ ] Encrypt inbound account secrets (TLS + payload encryption)
- [ ] Encrypt stored secrets in DB (AES or pgcrypto)
- [ ] Abstract token storage behind a `SecretsStore` interface
  - Initial: DB-based
  - Future: swap in AWS/GCP secrets manager
- [ ] All public API routes must:
  - Validate caller identity (JWT or token header)
  - Scope data access by `hostaway_account_id`
  - Enforce that users only access their listings/reservations

---

### ✉️ Task 6: Send Message API

- [ ] `/send-message`
- [ ] Accept: `reservation_id`, `message`, `channel_type`
- [ ] Lookup account credentials
- [ ] Call Hostaway messaging endpoint
- [ ] Log response, success/failure

---

### 🛡 Task 7: Production Hardening

- [ ] Healthcheck route `/health`
- [ ] Service logging: structured + account scoped
- [ ] Monitoring stubs: uptime, job failure logs
- [ ] Graceful shutdown handling for daemon
- [ ] Add `Makefile` targets: `make start`, `make sync`, `make run-daemon`
- [ ] Runtime config: `.env`, dotenv, scaffold for Vault/secrets switch
