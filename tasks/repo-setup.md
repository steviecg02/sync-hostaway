# Repository Setup & Infrastructure

**Goal:** Bring repository tooling up to industry standards

**Last Updated:** 2025-10-21

---

## Critical Setup Tasks (P0)

### 1. Fix Test Environment
**Status:** ✅ Should be in P0 critical tasks

See `tasks/p0-critical.md` #1

---

## High Priority Setup (P1)

### 1. Add CI/CD Pipeline
**Status:** No `.github/workflows/` directory exists
**Impact:** No automated testing on PR/push

**Requirements:**
- GitHub Actions workflow
- Run on push to main/develop and all PRs
- Jobs:
  - Lint (ruff, black)
  - Type check (mypy)
  - Tests (pytest with coverage)
  - Optional: Build Docker image

**Effort:** 2-3 hours

**See:** `tasks/p2-medium.md` #4 for implementation

---

### 2. Auto-Install Pre-Commit Hooks
**Status:** Config exists, manual installation required
**Impact:** Developers must remember to run `pre-commit install`

**Current:**
- `.pre-commit-config.yaml` exists ✅
- Hooks configured (black, ruff, mypy) ✅
- Manual installation: `pre-commit install`

**Solution:**
Update Makefile:
```makefile
install-dev:
	pip install -r requirements.txt -r dev-requirements.txt
	pre-commit install  # Auto-install hooks

venv:
	python3 -m venv venv && source venv/bin/activate && make install-dev
```

**Verification:**
```bash
make venv
# Should see: "pre-commit installed at .git/hooks/pre-commit"
```

**Effort:** 30 minutes

**Files to Modify:**
- `Makefile`
- `README.md` (update setup docs)

**See:** `tasks/p1-high.md` #4

---

### 3. Add Code Coverage Reporting
**Status:** Pytest configured, no coverage reporting

**Requirements:**
- Coverage.py integration
- HTML reports for local development
- CI integration (Codecov or Coveralls)
- Badge in README

**Setup:**
```bash
# Already in dev-requirements.txt
pytest-cov

# Generate reports
pytest --cov=sync_hostaway --cov-report=html --cov-report=term

# View: open htmlcov/index.html
```

**CI Integration:**
```yaml
# .github/workflows/ci.yml
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

**README Badge:**
```markdown
[![codecov](https://codecov.io/gh/user/repo/branch/main/graph/badge.svg)](https://codecov.io/gh/user/repo)
```

**Effort:** 1 hour

**Files to Create/Modify:**
- `.github/workflows/ci.yml` (add coverage upload)
- `README.md` (add badge)
- `.coveragerc` (optional - coverage config)

---

## Medium Priority Setup (P2)

### 1. Improve Docker Compose Configuration
**Status:** Basic setup exists, could be enhanced

**Current:**
```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"

  app:
    build: .
    depends_on:
      - postgres
    env_file: .env
```

**Enhancements:**

#### Add Volume Persistence
```yaml
  postgres:
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

#### Add PgAdmin (Optional)
```yaml
  pgadmin:
    image: dpage/pgadmin4
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@admin.com
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
```

#### Add Redis (If implementing token cache)
```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

**Effort:** 1 hour

**Files to Modify:**
- `docker-compose.yml`

---

### 2. Add EditorConfig
**Status:** Missing
**Impact:** Inconsistent editor settings across team

**Create `.editorconfig`:**
```ini
# .editorconfig
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4
max_line_length = 100

[*.{yml,yaml}]
indent_style = space
indent_size = 2

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
```

**Effort:** 15 minutes

**Files to Create:**
- `.editorconfig`

---

### 3. Add .gitignore Enhancements
**Status:** Basic .gitignore exists, could be more comprehensive

**Add:**
```gitignore
# .gitignore

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.mypy_cache/
.ruff_cache/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local
.env.*.local

# Alembic
alembic/versions/*.pyc

# Docker
*.log

# Coverage
coverage.xml
.coverage.*
```

**Effort:** 10 minutes

**Files to Modify:**
- `.gitignore`

---

### 4. Add Issue and PR Templates
**Status:** Missing
**Impact:** Inconsistent issue/PR formatting

**Issue Template:**
```markdown
<!-- .github/ISSUE_TEMPLATE/bug_report.md -->
---
name: Bug Report
about: Report a bug in sync-hostaway
---

## Bug Description
<!-- Clear description of the bug -->

## Steps to Reproduce
1.
2.
3.

## Expected Behavior
<!-- What should happen? -->

## Actual Behavior
<!-- What actually happens? -->

## Environment
- Python version:
- OS:
- Branch/Commit:

## Logs
```
<!-- Paste relevant logs -->
```

## Additional Context
<!-- Screenshots, related issues, etc. -->
```

**PR Template:**
```markdown
<!-- .github/PULL_REQUEST_TEMPLATE.md -->
## Description
<!-- What does this PR do? -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactoring
- [ ] Documentation
- [ ] Tests

## Checklist
- [ ] Tests pass locally (`make test`)
- [ ] Type checking passes (`mypy sync_hostaway/`)
- [ ] Linting passes (`make lint`)
- [ ] Coverage maintained or increased
- [ ] Documentation updated (if needed)
- [ ] Added tests for new functionality

## Related Issues
<!-- Closes #123 -->

## Screenshots (if applicable)
```

**Effort:** 30 minutes

**Files to Create:**
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`
- `.github/PULL_REQUEST_TEMPLATE.md`

---

## Low Priority Setup (P3)

### 1. Add Dependabot
**Status:** Not configured
**Impact:** Automated dependency updates

**Create `.github/dependabot.yml`:**
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    reviewers:
      - "team-reviewers"

  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
```

**Effort:** 15 minutes

**Files to Create:**
- `.github/dependabot.yml`

---

### 2. Add CODEOWNERS
**Status:** Not configured
**Impact:** Automatic PR reviewer assignment

**Create `.github/CODEOWNERS`:**
```
# Global owners
* @team-leads

# Specific areas
/sync_hostaway/network/ @network-team
/sync_hostaway/db/ @database-team
/tests/ @qa-team
```

**Effort:** 10 minutes

**Files to Create:**
- `.github/CODEOWNERS`

---

### 3. Add Setup.py or pyproject.toml Package Config
**Status:** pyproject.toml exists but minimal

**Current:** Only tool configs (black, ruff, mypy, pytest)

**Enhancement:** Add package metadata

**Option 1: Enhance pyproject.toml (Modern)**
```toml
# pyproject.toml
[project]
name = "sync-hostaway"
version = "1.0.0"
description = "Hostaway API sync service"
authors = [{name = "Your Team", email = "team@example.com"}]
requires-python = ">=3.11"
dependencies = [
    "alembic==1.16.4",
    "fastapi==0.116.1",
    # ... copy from requirements.txt
]

[project.optional-dependencies]
dev = [
    "black==25.1.0",
    "mypy==1.10.0",
    # ... copy from dev-requirements.txt
]

[build-system]
requires = ["setuptools>=65.0", "wheel"]
build-backend = "setuptools.build_meta"
```

**Option 2: Add setup.py (Classic)**
```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="sync-hostaway",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        # Copy from requirements.txt
    ],
    extras_require={
        "dev": [
            # Copy from dev-requirements.txt
        ]
    },
    python_requires=">=3.11",
)
```

**Benefits:**
- Enables `pip install -e .` (editable install)
- Fixes test import issues
- Standard Python packaging

**Effort:** 1 hour

**Files to Modify:**
- `pyproject.toml` (Option 1)
- OR create `setup.py` (Option 2)

---

### 4. Add Make targets for Common Operations
**Status:** Good Makefile exists, could add more targets

**Additional Targets:**
```makefile
.PHONY: coverage typecheck check

coverage:
	PYTHONPATH=. pytest --cov=sync_hostaway --cov-report=html --cov-report=term
	@echo "Coverage report: htmlcov/index.html"

typecheck:
	mypy sync_hostaway/

check: format lint typecheck test
	@echo "All checks passed!"

run-migrations:
	alembic upgrade head

create-migration:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"
```

**Effort:** 30 minutes

**Files to Modify:**
- `Makefile`

---

## Summary: Repository Infrastructure Status

| Component | Status | Priority | Effort |
|-----------|--------|----------|--------|
| Pre-commit config | ✅ Exists | - | - |
| Pre-commit auto-install | ❌ Manual | P1 | 30 min |
| CI/CD pipeline | ❌ Missing | P1 | 2-3 hrs |
| Test environment | ❌ Broken | P0 | 15 min |
| Coverage reporting | 🔄 Partial | P1 | 1 hr |
| Docker Compose | ✅ Basic | P2 | 1 hr |
| EditorConfig | ❌ Missing | P2 | 15 min |
| .gitignore | ✅ Basic | P2 | 10 min |
| Issue templates | ❌ Missing | P2 | 30 min |
| PR template | ❌ Missing | P2 | 30 min |
| Dependabot | ❌ Missing | P3 | 15 min |
| CODEOWNERS | ❌ Missing | P3 | 10 min |
| Package config | 🔄 Minimal | P3 | 1 hr |
| Make targets | ✅ Good | P3 | 30 min |

**Legend:**
- ✅ Complete
- 🔄 Partial
- ❌ Missing

---

## Recommended Implementation Order

### Phase 1 (P0-P1) - Critical Infrastructure
1. Fix test environment (P0)
2. Auto-install pre-commit hooks (P1)
3. Add CI/CD pipeline (P1)
4. Add coverage reporting (P1)

**Total Effort:** ~4 hours

### Phase 2 (P2) - Quality of Life
1. Enhance Docker Compose
2. Add EditorConfig
3. Enhance .gitignore
4. Add issue/PR templates

**Total Effort:** ~2 hours

### Phase 3 (P3) - Nice to Have
1. Add Dependabot
2. Add CODEOWNERS
3. Enhance package config
4. Add Make targets

**Total Effort:** ~2.5 hours

---

## Cross-Reference

- **Testing Setup:** See `tasks/p0-critical.md` #1
- **CI/CD Details:** See `tasks/p2-medium.md` #4
- **Pre-commit Details:** See `tasks/p1-high.md` #4
- **Full Infrastructure Audit:** See `docs/implementation-status.md`
