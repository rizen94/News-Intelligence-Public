# Agent Guidance

> Read `.clinerules/workflow.md` for how to approach problems. This file is for project-specific reference points only.

---

## Key Directories

| Area | Location |
|------|----------|
| API layer | `api/` — domain routes, services, DB connection module |
| Frontend | `web/src/` — SPA app code |
| Database migrations | `api/database/migrations/` |
| Config / env | `.env*`, `docker-compose*.yml` at project root |
| Docs | `docs/` — design docs, runbooks |
| Archive (cold) | `archive/` — retired code, old UI |

## Runtime Reference

| Role | Path / Host |
|------|-------------|
| Dev workspace | See current working directory |
| Production runtime | Project-specific — check deployment notes |
| Database | Check `api/shared/database/connection.py` for pool config |

## Product Roots

Check `web/src/` entry points for route mapping. See `.clinerules/workflow.md` for agent workflow rules.

---

*Keep this file minimal — add entries only when a path or host comes up repeatedly.*
