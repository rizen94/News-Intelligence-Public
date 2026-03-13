# v6 Planning — Claude-Ready Context

This folder contains consolidated project context for developing the v6 project plan. All documents are formatted for easy consumption by Claude or other AI advisors.

## Contents

| File | Purpose |
|------|---------|
| [00_OVERVIEW.md](00_OVERVIEW.md) | High-level project overview: architecture, tech stack, domains, capabilities |
| [01_HTML_REACT_SETTINGS.md](01_HTML_REACT_SETTINGS.md) | HTML entry point, package.json, vite.config, tsconfig, App.tsx routing |
| [02_DATABASE_SCHEMA.md](02_DATABASE_SCHEMA.md) | Database schema in readable format: domains, tables, migrations |
| [ORCHESTRATOR_V6_IMPLEMENTATION_PLAN.md](ORCHESTRATOR_V6_IMPLEMENTATION_PLAN.md) | Original parsed to-do list (superseded by Development Plan) |
| [ORCHESTRATOR_V6_DEVELOPMENT_PLAN.md](ORCHESTRATOR_V6_DEVELOPMENT_PLAN.md) | **Build-ready development plan** (contract, schema, lifecycle, testing) |
| [ORCHESTRATOR_V6_TECHNICAL_REVIEW.md](ORCHESTRATOR_V6_TECHNICAL_REVIEW.md) | Technical review (corrections and improvements) |

## Usage

When planning v6 features or refactors:

1. Start with `00_OVERVIEW.md` for system context
2. Use **`ORCHESTRATOR_V6_DEVELOPMENT_PLAN.md`** as the single source of truth for building the new controller system
3. Use `01_HTML_REACT_SETTINGS.md` for frontend layout, routes, and config
4. Use `02_DATABASE_SCHEMA.md` for existing data model; new orchestration/intelligence schemas are in the Development Plan and migrations 140/141

## Source of Truth

These documents are derived from:

- `docs/ARCHITECTURE_AND_OPERATIONS.md`
- `docs/PROJECT_CAPABILITIES_BRIEF.md`
- `docs/DOCS_INDEX.md`
- `web/index.html`, `web/package.json`, `web/vite.config.mts`, `web/tsconfig.json`, `web/src/App.tsx`
- `api/database/migrations/*.sql`, `docs/DATABASE_SCHEMA_DOCUMENTATION.md`

Update this folder when significant changes are made to the main codebase.
