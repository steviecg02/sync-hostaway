# Sync Hostaway

[![CI/CD](https://github.com/steviecg02/sync-hostaway/actions/workflows/ci.yml/badge.svg)](https://github.com/steviecg02/sync-hostaway/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/steviecg02/sync-hostaway/branch/main/graph/badge.svg)](https://codecov.io/gh/steviecg02/sync-hostaway)

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

# Note: Pre-commit hooks are automatically installed with make install-dev
# They will run on every git commit to enforce code quality
```

**2. Create `.env` file from template:**

```bash
cp .env.example .env
# Edit .env with your configuration
```

The `.env.example` file contains all required environment variables with documentation.

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

## Production Deployment (Using Pre-built Container)

**Pull the latest image from GitHub Container Registry:**

```bash
# Pull latest image
docker pull ghcr.io/steviecg02/sync-hostaway:latest

# Or pull a specific commit
docker pull ghcr.io/steviecg02/sync-hostaway:main-67fbfd7
```

**Run with docker-compose:**

```bash
# Create .env file with your configuration
# Then run:
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop
docker-compose down
```

**Container images are automatically built and pushed to GitHub Container Registry on every push to `main`.**

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

Pre-commit hooks are automatically installed with `make install-dev` and will run on every commit to enforce:
- Code formatting (black)
- Linting (ruff)
- Type checking (mypy)
- File formatting (trailing whitespace, end of files)

**Manual quality checks:**

```bash
# Format code
make format

# Run all linters and checks
make lint

# Type check only
mypy sync_hostaway/
```

**Bypass hooks (use sparingly):**
```bash
# Skip pre-commit hooks for a specific commit
git commit --no-verify -m "message"
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

## API Endpoints

All API routes are prefixed with `/api/v1/`.

### Account Management
- `POST /api/v1/hostaway/accounts` - Create new account and trigger sync
- `GET /api/v1/hostaway/accounts/{id}` - Get account details
- `PATCH /api/v1/hostaway/accounts/{id}` - Update account credentials
- `DELETE /api/v1/hostaway/accounts/{id}` - Delete account (soft or hard delete)
- `POST /api/v1/hostaway/accounts/{id}/sync` - Manually trigger sync

### Webhooks
- `POST /api/v1/hostaway/webhooks` - Receive Hostaway webhook events

### Monitoring
- `GET /health` - Health check (liveness probe)
- `GET /ready` - Readiness check (database connectivity)
- `GET /metrics` - Prometheus metrics

---

## Project Status

This is a production-ready Hostaway sync service with:
- ✅ Complete account management API
- ✅ Webhook system with auto-provisioning
- ✅ Full test suite (68 tests, 77% coverage)
- ✅ CI/CD pipeline with Docker builds
- ✅ Observability (metrics, structured logging, request tracing)
- ✅ Type-safe codebase (mypy strict mode)

For detailed implementation status and remaining tasks, see the `tasks/` directory.
