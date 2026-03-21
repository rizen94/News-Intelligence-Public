# News Intelligence — Architecture & Operations

**Version:** v8.0 (stable)  
**Last updated:** 2026-03-16

**Related:** [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) (routes and UI map) · [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) (pipeline stages) · [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md) · [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md)

---

## Architecture Overview

Three-machine setup:

| Machine | IP | Role |
|---------|-----|------|
| **Primary** | <PRIMARY_HOST_IP> | API, ML, Ollama, Redis, Frontend |
| **Widow** | <WIDOW_HOST_IP> | PostgreSQL, RSS worker, DB backups |
| **NAS** | <NAS_HOST_IP> | Storage only (no PostgreSQL) |

### Data Flow

- **Primary** runs the FastAPI app, connects to Widow’s database over LAN
- **Widow** runs PostgreSQL and the RSS collector (systemd), backs up to local (or NAS if mounted)
- **NAS** is used for archives/backups; no application logic

---

## Quick Start

```bash
./start_system.sh    # Start API, frontend, Redis
./status_system.sh   # Check all services
./stop_system.sh     # Stop API and frontend (keeps DB/Redis)
```

**URLs**

- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/system_monitoring/health

---

## Database Configuration

**Primary config (Widow):**

- Host: <WIDOW_HOST_IP>
- Port: 5432
- Database: news_intel
- User: newsapp
- Password: in `.db_password_widow` or `.env` as `DB_PASSWORD`

**Rollback to NAS (if needed):**

1. Start PostgreSQL on NAS (Package Center or `systemctl start postgresql`)
2. In `.env`: `DB_HOST=localhost`, `DB_PORT=5433`, `DB_NAME=news_intelligence`, `DB_PASSWORD=newsapp_password`
3. Run `./scripts/setup_nas_ssh_tunnel.sh`
4. Restart app

---

## Widow (Secondary)

**Services**

- PostgreSQL 16 (system service)
- RSS worker: `newsplatform-secondary.service` (every 10 min)
- Backups: cron at 03:00 daily, 04:00 Sun weekly

**SSH**

```bash
ssh widow   # or ssh user@<WIDOW_HOST_IP>
```

**Common commands**

```bash
# On Widow
sudo systemctl status newsplatform-secondary
sudo systemctl status postgresql
./scripts/db_backup.sh   # Manual backup
```

---

## Key Scripts

| Script | Purpose |
|--------|---------|
| `start_system.sh` | Start all services |
| `stop_system.sh` | Stop API and frontend |
| `status_system.sh` | Status of all components |
| `scripts/deploy_to_widow.sh` | Deploy code to Widow |
| `scripts/configure_widow_no_sleep.sh` | Disable Widow sleep (run on Widow) |
| `scripts/decommission_nas_postgresql.sh` | Stop NAS PostgreSQL |

---

## Data pipeline and automations

When the API is running (`./start_system.sh`), the following run **without manual triggers**:

| Component | What runs | Trigger |
|-----------|-----------|--------|
| **OrchestratorCoordinator** | Assess → plan → execute → learn every 60s | FastAPI lifespan |
| **Collection** | RSS fetch when CollectionGovernor recommends (min interval 5 min) | Coordinator loop |
| **Collection** | Finance refresh (gold/silver/platinum) when governor recommends | Coordinator loop |
| **AutomationManager** | All phases on intervals (rss_processing 30 min, article_processing 5 min, digest_generation 1 hr, etc.) | Background thread + scheduler |
| **Processing** | One phase per cycle via ProcessingGovernor (importance + watchlist) | Coordinator calls `automation.request_phase()` |
| **Finance orchestrator** | Scheduled refresh and queue worker | FastAPI lifespan |
| **Digest** | Weekly digest when phase runs (digest_generation depends on timeline_generation) | AutomationManager phase |
| **Health monitor** | Polls health feeds, creates alerts on failure | FastAPI lifespan |
| **Storyline consolidation** | Periodic consolidation (configurable interval) | Background thread |
| **Route supervisor** | Route and DB connection monitoring | Background thread |

**Optional (feature-flagged):**

- **Newsroom Orchestrator v6** (reporter_tick → ARTICLE_INGESTED, journalist/editor/archivist/chief_editor): only runs if `newsroom.enabled` is true in `api/config/newsroom.yaml` or `NEWSROOM_ORCHESTRATOR_ENABLED=1`. Default is disabled.

**Cron / external:** Optional. `scripts/rss_collection_with_health_check.sh` can be used as a fallback (e.g. if API is down); when the API is up, RSS is driven by the coordinator and AutomationManager.

**Confidence:** The data pipeline is fully connected for normal operation: start the system and collection, processing, digest, and downstream phases run on their schedules and governor recommendations. No manual trigger is required so long as the system is on and DB/LLM are available.

### Monitor page and pipeline (v8.1)

- **Migration 171** — `intelligence.tracked_events` has an optional `storyline_id` (VARCHAR 255) so tracked events can be linked to storylines for synthesis. Run once: `PYTHONPATH=api .venv/bin/python api/scripts/run_migration_171.py`.
- **Claims→facts task** — AutomationManager runs `claims_to_facts` (after `claim_extraction`, interval 1h). It promotes high-confidence extracted claims to `versioned_facts`, which fires the story-state trigger chain (`fact_change_log` → storyline_states). Visible in the Monitor **Phase timeline** and in the **Run phase now** dropdown.
- **Domain synthesis & enrichment card** — The Monitor page shows a card "Domain synthesis & enrichment" with domain configs (politics, finance, science-tech), GDELT enrichment status, and the last run of the claims→facts bridge.
- **Backlog priority removed** — The previous "enrichment backlog first" behaviour (gate other phases when content_enrichment backlog &gt; 0) is disabled; the pipeline cycle runs all phases on their intervals without that gate.

---

## Troubleshooting

**DB connection fails**

- Confirm Widow is on (ping <WIDOW_HOST_IP>)
- If Widow sleeps: run `scripts/configure_widow_no_sleep.sh` on Widow

**API won’t start**

- Check `.env` has `DB_PASSWORD` or `.db_password_widow` exists
- Confirm DB: `pg_isready -h <WIDOW_HOST_IP> -p 5432 -U newsapp`

**Widow RSS worker stopped**

```bash
ssh widow "sudo systemctl restart newsplatform-secondary"
```
