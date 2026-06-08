# News Intelligence — Architecture & Operations

**Version:** v8.0 (stable)  
**Last updated:** 2026-06-06

**Related:** [PROJECT_STATUS.md](../PROJECT_STATUS.md) · [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) · [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) · [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md) · [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md)

---

## Architecture overview (post-migration, June 2026)

The full News Intelligence stack runs on **Widow**. PopOS hosts HomeLab only. See [PROJECT_BOUNDARIES.md](../../PROJECT_BOUNDARIES.md) for the NI vs HomeLab split.

| Machine | IP | Role |
|---------|-----|------|
| **Widow** | `192.168.93.101` | Full NI stack: API, frontend, Postgres, automation, local Ollama (GTX 1080 8 GB) |
| **PopOS** | `192.168.93.99` | HomeLab AI Stack; **Caddy** WAN `:80/:443`; RTX **5090** Ollama for 70B narrative finisher |
| **NAS** | `192.168.93.100` | CIFS `/mnt/nas` — storage and backups only (no GPU) |

### Public HTTPS (PopOS Caddy → Widow)

WAN **443** terminates on **PopOS Caddy** (`ai-lab-caddy`). Hostname `news-intelligence-ag.duckdns.org` proxies to **Widow nginx** (`192.168.93.101`); Open WebUI uses `legion-agent.duckdns.org` on the same Caddy instance. See [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md).

### Widow paths

| Path | Role |
|------|------|
| `/home/pete/Documents/projects/News Intelligence` | Dev workspace (canonical) |
| `/opt/news-intelligence` | Production runtime (API on `:8000`) |
| `/home/pete/projects/News Intelligence` | Deprecated duplicate — do not use |

### Data flow

- **Widow** runs FastAPI, frontend, automation, and PostgreSQL locally (`localhost:5432/news_intel`)
- **70B narrative finisher** routes to **PopOS** (`OLLAMA_POP_OS_HOST=http://192.168.93.99:11434`) — RTX 5090
- **Public demo:** PopOS Caddy → Widow nginx → SPA + `/api/` (see [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md))
- **HomeLab** on PopOS reads NI data read-only via Postgres MCP (`NEWS_INTEL_DATABASE_URI` → Widow `:5432`)

---

## Quick start (on Widow)

**Production** — use systemd (survives reboot):

```bash
sudo systemctl start news-intelligence.target
/opt/news-intelligence/scripts/verify_widow_boot.sh
```

Install once: [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md).

**Dev only** — local frontend + manual processes (do **not** run alongside production API):

```bash
cd "/home/pete/Documents/projects/News Intelligence"
./start_system.sh   # WARNING: spawns duplicate AutomationManager if API already running
```

**URLs**

- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/system_monitoring/health

---

## Database configuration

**Canonical (Widow, local):**

| Setting | Value |
|---------|-------|
| Host | `localhost` (on Widow) or `192.168.93.101` (from remote clients) |
| Port | `5432` |
| Database | `news_intel` |
| User | `newsapp` |
| Password | Widow `configs/.env` (`DB_PASSWORD`) or `.db_password_widow` |

**Code single source of truth:** `api/shared/database/connection.py`  
**Schema:** `api/database/migrations/` — see [DATABASE.md](DATABASE.md)

**Legacy emergency rollback (NAS tunnel only — do not use for normal ops):**

1. Start PostgreSQL on NAS
2. In `.env`: `DB_HOST=localhost`, `DB_PORT=5433`, `DB_NAME=news_intelligence` (legacy name)
3. Run `./scripts/setup_nas_ssh_tunnel.sh`
4. Restart app

---

## Widow services

- PostgreSQL 16 (system service)
- RSS worker: `newsplatform-secondary.service` (every 10 min)
- DB backups: cron **03:00 daily** — `news_intel_latest.pgdump` under `/mnt/nas/Data Lake Storage/news-intelligence/database-backup/`

**SSH**

```bash
ssh widow   # or ssh pete@192.168.93.101
```

**Common commands (on Widow)**

```bash
sudo systemctl status newsplatform-secondary
sudo systemctl status postgresql
./scripts/db_backup_single_latest.sh
```

---

## Key scripts

| Script | Purpose |
|--------|---------|
| `start_system.sh` | Start all services |
| `stop_system.sh` | Stop API and frontend |
| `status_system.sh` | Status of all components |
| `scripts/deploy_to_widow.sh` | Deploy code to Widow |
| `scripts/configure_widow_no_sleep.sh` | Disable Widow sleep |
| `scripts/decommission_nas_postgresql.sh` | Stop NAS PostgreSQL |

---

## Data pipeline and automations

When the API is running (`./start_system.sh`), the following run **without manual triggers**:

| Component | What runs | Trigger |
|-----------|-----------|--------|
| **OrchestratorCoordinator** | Assess → plan → execute → learn every 60s | FastAPI lifespan |
| **Collection** | RSS fetch when CollectionGovernor recommends (min interval 5 min) | Coordinator loop |
| **Collection** | Finance refresh when governor recommends | Coordinator loop |
| **AutomationManager** | All phases on intervals | Background thread + scheduler |
| **Processing** | One phase per cycle via ProcessingGovernor | Coordinator |
| **Finance orchestrator** | Scheduled refresh and queue worker | FastAPI lifespan |
| **Digest** | Weekly digest when phase runs | AutomationManager |
| **Health monitor** | Polls health feeds, creates alerts | FastAPI lifespan |
| **Storyline consolidation** | Periodic consolidation | Background thread |
| **Route supervisor** | Route and DB connection monitoring | Background thread |

**Optional:** Newsroom Orchestrator v6 — only if `newsroom.enabled` in config or `NEWSROOM_ORCHESTRATOR_ENABLED=1`.

---

## Troubleshooting

**DB connection fails**

- Confirm Widow is on: `ping 192.168.93.101`
- If Widow sleeps: run `scripts/configure_widow_no_sleep.sh` on Widow
- Check: `pg_isready -h localhost -p 5432 -U newsapp`

**API won't start**

- Check `.env` has `DB_PASSWORD` or `.db_password_widow` exists
- Confirm production tree at `/opt/news-intelligence` vs dev tree drift

**Widow RSS worker stopped**

```bash
ssh widow "sudo systemctl restart newsplatform-secondary"
```
