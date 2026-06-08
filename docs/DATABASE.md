# Database — News Intelligence

**Canonical reference** for PostgreSQL configuration, schema layout, and connection rules. **No passwords in this file** — see [SECRETS_AND_SETTINGS_INDEX.md](SECRETS_AND_SETTINGS_INDEX.md).

---

## Connection

| Setting | Value |
|---------|-------|
| Host | `localhost` on Widow; `192.168.93.101` from remote clients |
| Port | `5432` |
| Database | `news_intel` |
| User | `newsapp` |
| Password | Widow `configs/.env` (`DB_PASSWORD`) or `.db_password_widow` |

**Code single source of truth:** `api/shared/database/connection.py`  
**Env vars:** `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (project-root `.env` or `configs/.env`)

**Shim:** `config/database.py` re-exports for backward compatibility.

---

## Ownership

News Intelligence **owns** the `news_intel` database on Widow. HomeLab AI Stack on PopOS connects read-only via Postgres MCP (`NEWS_INTEL_DATABASE_URI`). Homelab's local Postgres on port `15432` is a **separate** database for Open WebUI/stack profile — not NI data.

---

## Schema layout

- **Per-domain schemas:** `politics`, `finance`, `science_tech`, plus YAML-provisioned silos
- **Global schemas:** `public`, `intelligence`, `pipeline` (and others per migrations)
- **Migrations:** `api/database/migrations/` — see `api/database/migrations/README.md`
- **Verification:** `PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py`

Key tables (non-exhaustive):

| Area | Tables |
|------|--------|
| Domains | `public.domains` |
| Per-domain | `{schema}.articles`, `{schema}.storylines`, `{schema}.rss_feeds`, `{schema}.events` |
| Intelligence | `intelligence.entity_profiles`, `intelligence.versioned_facts`, `intelligence.content_refinement_queue` |
| Automation | `public.automation_run_history` |
| Pipeline | `pipeline_traces`, `pipeline_checkpoints` |

---

## Connection pools

Four psycopg2 pools + SQLAlchemy (see `connection.py`):

| Pool | Purpose | Env vars |
|------|---------|----------|
| UI | Page loads, monitoring | `DB_POOL_UI_MIN/MAX` |
| Worker | Automation, batch | `DB_POOL_WORKER_MIN/MAX` |
| Health | Health probes | `DB_POOL_HEALTH_MIN/MAX` |
| SA | ORM services | `DB_POOL_SA_SIZE/OVERFLOW` |

Rules:

1. Use `get_db_connection_context()` — always close connections.
2. Never hold connections across LLM calls, HTTP, or sleeps.
3. Total pool max across all processes must stay under PostgreSQL `max_connections`.

See [PGBOUNCER_AND_CONNECTION_BUDGET.md](PGBOUNCER_AND_CONNECTION_BUDGET.md) and [CODING_STYLE_GUIDE.md](CODING_STYLE_GUIDE.md).

---

## Backups

- **Policy:** Rolling `news_intel_latest.pgdump` to NAS — see [DATABASE_BACKUP.md](DATABASE_BACKUP.md)
- **Script:** `scripts/db_backup_single_latest.sh` (on Widow)

---

## Legacy emergency rollback

NAS tunnel rollback (`DB_PORT=5433`, legacy DB name `news_intelligence`) is **emergency only**. Canonical name is `news_intel`. See [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md).

---

## Related docs

- [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md)
- [DB_PRODUCTION_MAINTENANCE_RUNBOOK.md](DB_PRODUCTION_MAINTENANCE_RUNBOOK.md)
- [SECRETS_AND_SETTINGS_INDEX.md](SECRETS_AND_SETTINGS_INDEX.md)
- [../PROJECT_BOUNDARIES.md](../../PROJECT_BOUNDARIES.md)
