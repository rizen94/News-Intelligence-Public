# News Intelligence — Import Standards (Preventing 502 Regressions)

## Why This Matters

The **entire API** runs as a single Python package under `api/`. When any service module uses a broken bare import like:

```python
from services.X import Y        # BROKEN — no top-level "services" in sys.path
from shared.X import Y          # BROKEN — no top-level "shared" in sys.path
```

...the module fails to import at load time. FastAPI's `uvicorn` crashes or returns **502 Bad Gateway** for every endpoint that transitively depends on the broken module. Since many services have a shared dependency graph (database pool, logging config, LLM clients), **one broken import can take down the entire service**.

### What Happened (Root Cause)

The `api/` directory is structured as:

```
api/
├── main.py                 # Entry point: `from api.main import app`
├── services/               # Domain-specific services
│   └── X/                  ← "services" is a sub-package, NOT top-level
├── shared/                 # Shared utilities
│   └── Y/                  ← "shared" is a sub-package, NOT top-level
```

Python's import system resolves `from services.X` relative to the **current working directory** or paths in `sys.path`. Since uvicorn runs from the repo root (`/opt/news-intelligence/`) and only that path (plus `.venv/lib/python*/site-packages`) is on `sys.path`, the bare import `services.X` doesn't resolve.

The correct import is **absolute**:

```python
from api.services.X import Y   # CORRECT — resolves via api/ package hierarchy
from api.shared.Y import Z     # CORRECT — resolves via api/ package hierarchy
```

## The Fix Applied (Nov 5, 2026)

### Bulk Changes (sed)

Converted all bare/rerelative imports across **640 files**:

| Before | After |
|--------|-------|
| `from services.X import Y` | `from api.services.X import Y` |
| `from shared.X import Y` | `from api.shared.X import Y` |
| `from .services.X import Y` | `from api.services.X import Y` |

### Manual Edge Case

Cross-directory imports in `__init__.py` files where relative imports span multiple package levels were corrected individually. The sed pattern couldn't safely handle these without risking false matches on legitimate same-level imports.

## Prevention Rules

### 1. Always Use Absolute Imports Within `api/`

**Rule:** Every import inside the `api/` tree must be absolute, starting with `api.`:

```python
# ✅ CORRECT — always
from api.services.storyline_management.engine import StorylineEngine
from api.shared.database.pool import get_pool
from api.domains.news_aggregation.routes.articles import router

# ❌ WRONG — will break when service runs from repo root
from services.storyline_management.engine import StorylineEngine
from shared.database.pool import get_pool
from .services.storyline_management.engine import StorylineEngine  # sometimes works, fragile
```

### 2. Why Relative Imports Are Risky

- **Dev server** (uvicorn): `api.main:app` — relative imports *within* `api/` may work because Python sees the package namespace
- **Production** (or any context where working directory ≠ api/ root): relative imports break silently
- **Testing, CLI scripts, cron jobs**: all run from repo root → bare imports fail

**Bottom line:** Relative imports only work when you happen to be in the right directory. Absolute imports work everywhere.

### 3. Pre-Commit Checklist for Any API Change

Before committing any change to `api/`:

1. **Verify imports compile:**
   ```bash
   cd /path/to/news_intelligence
   python -c "import sys; sys.path.insert(0, '.'); from api.main import app"
   ```
   If this doesn't print `Import OK`, you have a broken import.

2. **No new bare imports:** Search for any `from services.` or `from shared.` in your diff:
   ```bash
   git diff --cached | grep "^+.*from services\\.\|^+.*from shared\\."
   ```

3. **Test the service:** Start uvicorn locally and hit `/api/system_monitoring/health` — returns 200 if imports are clean.

### 4. If You Need to Add a New Module

```python
# Create it with correct imports from line one:
# api/domains/new_domain/module.py
from api.services.other_service import SomeService    # always absolute
from api.shared.database.pool import get_pool          # always absolute
from api.main import app                               # never skip the "api." prefix
```

## Quick Reference: Current Package Structure

```
api/                          ← Python package root (sys.path entry)
├── main.py                  # FastAPI app entry point
├── config/                  # Config modules
├── domains/                 # Domain-specific code
│   ├── news_aggregation/
│   │   ├── routes/          # API route handlers
│   │   └── services/        # Domain business logic
│   ├── storyline_management/
│   │   ├── services/
│   │   └── ...
│   └── ...
├── shared/                  # Cross-domain utilities
│   ├── database/
│   ├── llm_clients/
│   ├── ...
│   └── services/
├── services/                # (legacy) — merged into domains/
├── scripts/                 # Internal scripts
└── tests/                   # Tests
```

## Emergency Recovery Procedure

If the service goes down with 502s after a deploy:

1. **Check uvicorn logs:** Look for `ModuleNotFoundError` or `ImportError` traces
2. **Search all Python files:** `grep -rn "from services\\.\|from shared\\." api/ --include="*.py" | grep -v __pycache__`
3. **Fix and restart:** Apply the absolute import fix, clear caches (`find . -type d -name __pycache__ -exec rm -rf {} +`), restart uvicorn

## File Count After Fix

- **640 files changed** in the bulk sed replacement (Nov 5, 2026)
- **1 file** manually corrected (cross-directory `__init__.py` edge case)
- **Net diff:** +2380/-2211 lines (mostly import line rewrites)
