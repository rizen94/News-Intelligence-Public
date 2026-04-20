---
name: Backend — Python API and services
description: FastAPI, services, shared modules under api/
alwaysApply: false
globs:
  - "api/**/*.py"
---

# Backend (`api/`)

- **Naming:** **`snake_case`** for files, functions, variables, route path segments, tables/columns.
- **Responses:** follow project **`APIResponse(success, data, message)`** patterns (see `docs/CODING_STYLE_GUIDE.md`).
- **Routes:** live under `api/domains/*/routes/` or global routers; mount at **`/api`** with **`snake_case`** segments.
- **Domains:** respect **`shared.domain_registry`** — avoid hardcoding a fixed list of three silos where shared iterators exist.
- **Logging:** use module **`logger`**, not print.
- **DB:** only **`shared.database.connection`** (or documented shims). See rule **`00-core-news-intelligence.md`** for pool and lifecycle rules.
- **Migrations:** active SQL in `api/database/migrations/`; follow repo migration README and verification scripts when adding DDL.
