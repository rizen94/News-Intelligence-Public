# News Intelligence

AI-powered news aggregation and analysis: RSS ingestion, storyline tracking, entity resolution, and intelligence delivery.

> **Migration complete (June 2026).** Active development is on **Widow** (`192.168.93.101`). See **[PROJECT_STATUS.md](PROJECT_STATUS.md)** before working in this repo.

## Quick links

| Doc | Purpose |
|-----|---------|
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | Host authority, paths, cold storage checklist |
| [AGENTS.md](AGENTS.md) | Agent terminology, entry points, DB rules |
| [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) | Full documentation index |
| [docs/ARCHITECTURE_AND_OPERATIONS.md](docs/ARCHITECTURE_AND_OPERATIONS.md) | Current architecture and ops |
| [docs/SETUP_ENV_AND_RUNTIME.md](docs/SETUP_ENV_AND_RUNTIME.md) | Install, env, startup |
| [../PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md) | NI vs HomeLab AI Stack split |

## Features

### Nightly Force Cycle
A temporary mechanism to bypass nightly pipeline restrictions and force all automation phases to run during catchup scenarios.

**Endpoint:** `/force_nightly_cycle?duration_hours=24`
**Usage:** `curl -X POST "http://localhost:8000/force_nightly_cycle?duration_hours=24"`

This feature is useful when you need to process backlog items that would normally be skipped during the nightly pipeline window.

## Stack

- **Backend:** FastAPI (`api/`)
- **Frontend:** React + TypeScript (`web/`)
- **Database:** PostgreSQL `news_intel` on Widow
- **LLM:** Ollama (local on Widow + 70B offload to main server)

## Start (on Widow)

```bash
cd "/home/pete/Documents/projects/News Intelligence"
./start_system.sh
```

- API: http://localhost:8000
- Frontend: http://localhost:3000
- Health: http://localhost:8000/api/system_monitoring/health
