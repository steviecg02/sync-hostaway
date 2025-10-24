# Container Build Testing

**Created:** 2025-10-24
**Priority:** P1 (High)
**Status:** Not Started

---

## Problem

During deployment of sync-airbnb, a required file was missing from the Docker image, causing the container to fail at runtime. The build succeeded but the container didn't work.

**We need to prevent this by:**
1. Actually running the built container in CI/CD (not just building it)
2. Testing that the container starts successfully
3. Verifying all required files are included

---

## Tasks

### 1. Update GitHub Actions Workflow

**File:** `.github/workflows/ci.yml` or similar

**Add steps to:**
- [ ] Build the Docker image
- [ ] Run the container with minimal health check
- [ ] Verify the container starts without errors
- [ ] Test critical endpoints (e.g., `/health`)

**Reference:** Check sync-airbnb repository for implementation details

---

### 2. Add Makefile Commands

**File:** `Makefile`

**Add targets for:**
- [ ] `make test-container` - Build and test container locally
- [ ] `make run-container` - Run container with proper env vars
- [ ] Container validation commands

**Reference:** Check sync-airbnb Makefile for examples

---

## Acceptance Criteria

- [ ] CI/CD pipeline builds AND runs the container
- [ ] CI/CD fails if container doesn't start successfully
- [ ] Makefile has easy commands to test containers locally
- [ ] Documentation updated if needed

---

## Notes

- Check sync-airbnb repo for reference implementation
- This prevents "builds but doesn't run" failures
- Critical for production deployments

---

**Next Steps:**
1. Review sync-airbnb GitHub Actions workflow
2. Review sync-airbnb Makefile
3. Implement similar testing here
