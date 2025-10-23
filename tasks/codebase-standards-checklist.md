# Codebase Standards Checklist

**Purpose:** Document all issues found and fixed in sync_airbnb codebase to ensure consistency across related projects.

**Legend:**
- ✅ **Completed** in sync_airbnb
- ⏳ **Remaining** work needed
- 🌍 **Universal** - Applies to all Python/FastAPI projects
- 🏠 **Project-Specific** - Specific to sync_airbnb architecture

---

## 1. Security

### 1.1 Authentication & Authorization

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P0-1 | No API authentication | Implement API key authentication on all endpoints (except health check) | Prevents unauthorized access, data theft, account manipulation, and DoS attacks | 🌍 Universal | ⏳ Remaining |

**Principle:** All production APIs must have authentication. Use API keys for service-to-service, OAuth2 for user-facing.

---

### 1.2 Secrets Management

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P0-4 | Hardcoded API keys in source code | Move all secrets to environment variables | Prevents exposure in git history, Docker images, logs; enables rotation without code deploy | 🌍 Universal | ✅ Completed |
| P0-5 | .env file security audit | Verify .env not in git history, create .env.example, ensure .gitignore includes .env | Prevents credential exposure in version control | 🌍 Universal | ✅ Completed |

**Principle:** Never hardcode secrets. Always use environment variables. Never commit .env files. Always provide .env.example templates.

---

## 2. Code Quality & Testing

### 2.1 Type Safety

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P1-6 | 28 mypy type errors | Add type annotations to all functions, fix SQLAlchemy model types, add None checks | Catches bugs at compile time, improves IDE autocomplete, documents expected types | 🌍 Universal | ✅ Completed |

**Principle:** Use static type checking (mypy). Annotate all function signatures. Use `Type | None` instead of `Optional[Type]`.

---

### 2.2 Test Coverage

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P0-2 | 15 failing tests (import paths) | Update all import paths after refactoring to `sync_airbnb.*` | Ensures tests actually run and catch regressions | 🌍 Universal | ✅ Completed |
| P0-3 | Missing JSON schema validation | Move schemas to tests/schemas/, validate API responses against schemas | Detects breaking API changes early, prevents malformed data in database | 🏠 Specific | ✅ Completed |

**Principle:** Keep tests passing. Update tests when refactoring. Aim for >80% coverage. Validate external API responses.

---

### 2.3 Input Validation

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P2-19 | Missing Pydantic field validators | Add field validators for account_id (numeric), airbnb_cookie (contains _user_attributes) | Catches invalid data at API boundary before it reaches database | 🌍 Universal | ✅ Completed |

**Principle:** Validate all inputs at the API boundary using Pydantic validators. Fail fast with clear error messages.

---

## 3. Architecture & Design

### 3.1 Layered Architecture

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| N/A | Enforce separation of concerns | Always follow: `api → services → (network/payloads/flatteners/parsers) → db → PostgreSQL` | Prevents business logic in routes, enables testing, improves maintainability | 🌍 Universal | ✅ Completed |

**Principle:**
- **API routes:** HTTP handling only, no business logic
- **Services:** Orchestration and business logic
- **Network/Payloads/Flatteners/Parsers:** Data transformation
- **Database:** SQL queries only, no business logic

Never skip layers. Never call database directly from API routes.

---

### 3.2 Dependency Injection

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| N/A | Pass dependencies as parameters | Always pass `engine: Engine` as function parameter instead of global | Enables testing with mock dependencies, makes dependencies explicit | 🌍 Universal | ✅ Completed |

**Principle:** Inject dependencies (database engines, HTTP clients) as function parameters. Avoid global state except for config.

---

### 3.3 Error Handling

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P1-9 | Single listing failure breaks entire sync | Wrap each listing in try/except, track succeeded/failed counts, continue on error | One bad listing doesn't prevent syncing other listings | 🏠 Specific | ✅ Completed |
| P2-17 | Inconsistent error responses | Standardize error format: `{"error": {"code", "message", "details", "request_id"}}` | Consistent error handling for API clients | 🌍 Universal | ✅ Completed |

**Principle:**
- Use specific exception types, not bare `except:`
- Log errors with context (account_id, listing_id, etc.)
- Return structured error responses
- Implement per-item error recovery for batch operations

---

## 4. Concurrency & Threading

### 4.1 Thread Safety

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P1-8 | Daemon threads killed mid-transaction | Use `daemon=False`, implement graceful shutdown with signal handlers, track active threads | Prevents data corruption, ensures transactions complete | 🌍 Universal | ✅ Completed |
| P1-12 | Scheduler thread safety concerns | Use APScheduler's BackgroundScheduler (thread-safe by design) | Prevents race conditions in scheduled jobs | 🌍 Universal | ✅ Completed |

**Principle:**
- Never use `daemon=True` for threads that modify data
- Always implement graceful shutdown (SIGTERM/SIGINT handlers)
- Use thread-safe libraries (APScheduler, SQLAlchemy)
- Track active threads for cleanup

---

## 5. Database

### 5.1 Connection Management

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P2-15 / P1-15 | Database connection pool configuration | Add `pool_pre_ping=True` and `pool_recycle=3600` to engine config | Prevents stale connection errors, handles network hiccups | 🌍 Universal | ✅ Completed |

**Principle:** Always configure connection pooling in production. Use pool_pre_ping to test connections before use.

---

### 5.2 Indexes

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P1-13 | Missing database indexes | Add indexes on: account_id, customer_id, is_active, deleted_at, and composite indexes on metrics tables | Improves query performance, enables efficient filtering | 🌍 Universal | ✅ Completed |

**Principle:** Add indexes on:
- Foreign keys
- Columns used in WHERE clauses
- Columns used in JOIN conditions
- Composite indexes for common query patterns

---

### 5.3 Soft Delete

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P3-26 | Hard delete (permanent data loss) | Implement soft delete with `deleted_at` timestamp, exclude deleted records by default, add restore endpoint | Enables recovery from accidental deletion, preserves audit trail | 🌍 Universal | ✅ Completed |

**Principle:** Use soft delete for user-facing data. Add `deleted_at` column. Filter with `WHERE deleted_at IS NULL` by default.

---

### 5.4 Migrations

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P2-21 | No migration testing process | Create migration test script that tests upgrade → downgrade → upgrade cycle | Ensures migrations are reversible and don't break in production | 🌍 Universal | ✅ Completed |

**Principle:** Always test migrations before production deploy. Test both upgrade and downgrade paths.

---

## 6. API Design

### 6.1 Documentation

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P3-23 | Missing OpenAPI documentation | Add comprehensive docstrings to all endpoints with examples, descriptions, response schemas | Improves developer experience, auto-generates Swagger UI | 🌍 Universal | ✅ Completed |
| P3-22 | No API versioning strategy | Document versioning policy: `/api/v{major}/`, deprecation process, sunset timeline | Enables breaking changes without breaking existing clients | 🌍 Universal | ✅ Completed |

**Principle:**
- Document all endpoints with OpenAPI/Swagger
- Use URL versioning (`/api/v1/`)
- Provide request/response examples
- Document error responses

---

### 6.2 Pagination

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P3-24 | No pagination on list endpoints | Implement offset/limit pagination with metadata (total, offset, limit, has_more) | Prevents slow responses and high memory usage with large datasets | 🌍 Universal | ✅ Completed |

**Principle:** Always paginate list endpoints. Return pagination metadata. Default to 50 items per page, max 100.

---

### 6.3 Data Export

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P3-28 | No metrics export capability | Add CSV/JSON export endpoints with date range filtering | Enables data analysis in BI tools (Excel, Tableau, etc.) | 🏠 Specific | ✅ Completed |

**Principle:** Provide export endpoints for datasets that users need to analyze externally. Support CSV (Excel-compatible) and JSON.

---

## 7. Observability & Logging

### 7.1 Logging Standards

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P2-14 | Emoji in logs | Remove all emoji from log messages | Breaks JSON log parsers, causes encoding issues | 🌍 Universal | ✅ Completed |
| N/A | Use structured logging | Always log with context: account_id, listing_id, request_id, error type | Enables filtering and debugging in production | 🌍 Universal | ✅ Completed |

**Principle:**
- Never use emoji in logs
- Never use `print()`, always use `logger.info/error/warning`
- Include context in all log messages
- Use JSON-structured logs in production

---

### 7.2 Request Tracing

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P2-18 | No request ID tracking | Add middleware to generate/extract request ID, include in all logs and error responses | Enables tracing requests across services and log aggregation | 🌍 Universal | ✅ Completed |

**Principle:** Generate unique request ID for each API call. Include in response headers and all logs.

---

### 7.3 Job Tracking

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P1-7 | No job status tracking | Create sync_jobs table to track job status, progress, errors | Enables monitoring long-running jobs, debugging failures | 🏠 Specific | ⏳ Remaining |

**Principle:** Track status of async/background jobs in database. Include start time, end time, status, error messages.

---

## 8. Date & Time Handling

### 8.1 Timezone Consistency

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P2-20 | Inconsistent datetime handling | Create `utc_now()` helper, always use timezone-aware datetimes, store in UTC | Prevents timezone bugs, ensures consistent timestamps | 🌍 Universal | ✅ Completed |

**Principle:**
- Always use timezone-aware datetimes
- Always store in UTC
- Never use `datetime.now()` or `datetime.utcnow()`
- Use `datetime.now(timezone.utc)` or `utc_now()` helper

---

## 9. Deployment & Operations

### 9.1 Docker Optimization

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P3-25 | Large Docker image size | Use multi-stage build: builder (gcc, build deps) + runtime (slim, runtime deps only) | Reduces image size 30-40%, faster deployments, lower costs | 🌍 Universal | ✅ Completed |

**Principle:**
- Use multi-stage Dockerfile
- Use `python:3.x-slim` base image
- Separate build dependencies from runtime dependencies
- Copy only necessary files

---

### 9.2 Configuration Management

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| N/A | Environment-based configuration | Support MODE env var (admin/worker/hybrid) for different deployment patterns | Enables single codebase for different deployment modes | 🏠 Specific | ✅ Completed |
| P2-16 | No dry-run mode | Add `INSIGHTS_DRY_RUN` env var to skip database writes for testing | Enables safe testing in production environment | 🌍 Universal | ✅ Completed |

**Principle:**
- Use environment variables for all configuration
- Support different modes for different deployment patterns
- Provide dry-run mode for testing

---

## 10. Rate Limiting & External APIs

### 10.1 Rate Limit Handling

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P1-10 | No rate limiting implementation | Add 429 detection with prominent logging, document wait-and-see strategy | Prevents hitting API rate limits, tracks when limits are hit | 🏠 Specific | ⏳ Remaining |

**Principle:**
- Always detect 429 responses from external APIs
- Log rate limit hits prominently
- Implement retry with exponential backoff
- Monitor rate limit headers (Retry-After, X-RateLimit-*)

**Decision:** For sync_airbnb, we documented a "wait and see" strategy - monitor after deployment to Nook, only implement rate limiting if 429s occur frequently.

---

## 11. Multi-Tenancy

### 11.1 Customer Isolation

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| P3-27 | No documentation for customer_id usage | Document multi-tenant patterns, query examples, use cases | Enables multi-customer deployments (SaaS, agency, internal teams) | 🏠 Specific | ✅ Completed |

**Principle:**
- Support multi-tenancy from day one
- Use UUID for customer/tenant IDs
- Add indexes on tenant columns
- Document tenant isolation patterns

---

## 12. Code Organization

### 12.1 Package Structure

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| N/A | Top-level modules | Refactor into proper package: all code under `sync_airbnb/` | Enables proper Python packaging, imports, and distribution | 🌍 Universal | ✅ Completed |

**Principle:**
- All source code under project package directory
- Use `__init__.py` files to define package structure
- Use absolute imports (`from sync_airbnb.x import y`)

---

### 12.2 Documentation

| # | Issue | Fix | Why | Type | Status |
|---|-------|-----|-----|------|--------|
| N/A | Missing project documentation | Create: CLAUDE.md (AI instructions), CONTRIBUTING.md (dev workflow), ARCHITECTURE.md (system design), implementation-status.md (current state) | Enables new developers to contribute, documents decisions | 🌍 Universal | ✅ Completed |

**Principle:** Every project needs:
- README.md - Quick start, setup, basic usage
- ARCHITECTURE.md - System design, data flow, key decisions
- CONTRIBUTING.md - Dev workflow, code standards, testing
- implementation-status.md - Current state, known issues
- CLAUDE.md (optional) - Instructions for AI assistants

---

## Summary Statistics

### By Priority
- **P0 (Critical):** 4/5 completed (80%)
- **P1 (High):** 6/8 completed (75%)
- **P2 (Medium):** 8/8 completed (100%)
- **P3 (Low):** 7/7 completed (100%)

### By Type
- **🌍 Universal (applies to all projects):** ~70% of issues
- **🏠 Project-Specific (sync_airbnb only):** ~30% of issues

### Overall Progress
- **Total Tasks:** 28
- **Completed:** 25 (89%)
- **Remaining:** 3 (11%)

---

## Remaining Work

Only 3 tasks remain:

1. **P0-1: API Authentication** (~4-8 hours)
   - Only critical blocker for production
   - Universal - every API needs auth

2. **P1-7: Job Status Tracking** (~3-4 hours)
   - Project-specific enhancement
   - Enables monitoring background jobs

3. **P1-10: Rate Limiting Implementation** (optional)
   - Project-specific
   - Strategy documented: wait and see if needed after deployment

---

## How to Use This Checklist

### For the Other Codebase:

1. **Go through each category** and check if that issue exists
2. **Focus on 🌍 Universal items** - these apply to all Python/FastAPI projects
3. **Skip 🏠 Project-Specific items** that don't apply (e.g., Airbnb API specifics)
4. **Adapt principles** to your specific use case

### Key Universal Principles to Check:

✅ **Security:**
- No hardcoded secrets
- Environment variables for all config
- API authentication

✅ **Code Quality:**
- Type annotations (mypy)
- Tests passing
- Input validation (Pydantic)

✅ **Architecture:**
- Layered architecture (no business logic in routes)
- Dependency injection
- Error handling with context

✅ **Database:**
- Connection pooling configured
- Indexes on foreign keys and filter columns
- Soft delete for user data

✅ **API Design:**
- OpenAPI documentation
- Pagination on lists
- Structured error responses

✅ **Operations:**
- Multi-stage Dockerfile
- Timezone-aware datetimes (UTC)
- Request ID tracking

---

## Questions for Cross-Codebase Comparison

When reviewing the other codebase, ask:

1. Does it have the same security issues? (hardcoded secrets, no auth)
2. Are tests passing? What's the coverage?
3. Does it follow layered architecture?
4. How does it handle errors? (per-item recovery?)
5. Are database connections properly pooled?
6. Does it have API documentation?
7. How are datetimes handled? (timezone-aware?)
8. Is the Docker image optimized?
9. Does it track request IDs?
10. How are background jobs monitored?

---

## Version History

- **v1.0** - Initial checklist based on sync_airbnb P0-P3 tasks (October 2025)
