---
created: 2026-04-20
updated: 2026-06-06
tags: [project, news-intelligence, production, fastapi, postgres, widow]
status: production-on-widow
---

# News Intelligence

> Multi-domain news ingestion, storyline tracking, entity resolution, and intelligence delivery.

## Status (June 2026)

- **Migration PopOS → Widow: COMPLETE AND FINAL**
- **Authoritative host:** Widow `192.168.93.101`
- **Dev workspace:** `/home/pete/Documents/projects/News Intelligence` on Widow
- **Production runtime:** `/opt/news-intelligence` on Widow (API `:8000`)
- **PopOS local copy:** cold storage → `/mnt/nas/News-Intelligence-Archive-2026-06-03`
- **Do not develop on PopOS local copy**

## Stack

- FastAPI + PostgreSQL (`news_intel`) + React frontend
- Ollama on Widow; 70B narrative finisher offloaded to `192.168.93.100`
- AutomationManager, RSS pipeline, per-domain schemas

## Database

- **Owns** `news_intel` on Widow `:5432` (user `newsapp`)
- HomeLab Postgres MCP on PopOS reads this **read-only** — not Homelab `:15432`

## Key entry points (Widow)

- `api/main.py` — API
- `api/shared/database/connection.py` — DB single source
- `api/services/automation_manager.py` — background automation
- `AGENTS.md`, `PROJECT_STATUS.md` — agent and ops authority

## Cross-project

- [[../40_Reference/project-boundaries-ni-homelab]]
- [[../30_Decisions/2026-06-06-ni-widow-migration-complete]]
- HomeLab integration: Postgres MCP, shared Ollama, MemPalace wing `news_intelligence`

## Longitudinal / execution

- [[news-intelligence-longitudinal-execution]] (if mirrored in vault)
- [[../10_Runbooks/06-longitudinal-phase-progress]]
