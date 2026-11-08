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
| Password | `DB_PASSWORD` from project-root `.env` or `configs/.env` |

**Code single source of truth:** `api/shared/database/connection.py`  
**Env vars:** `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` (project-root `.env` or `configs/.env`)

**Shim:** `config/database.py` re-exports for backward compatibility.

---

## Ownership

News Intelligence **owns** the `news_intel` database on Widow. HomeLab AI Stack on PopOS connects read-only via Postgres MCP (`NEWS_INTEL_DATABASE_URI`). Homelab's local Postgres on port `15432` is a **separate** database for Open WebUI/stack profile — not NI data.

---

## Schema layout

- **Per-domain schemas:** `politics`, `finance`, `legal`, `medicine`, `artificial_intelligence`, `neurodiversity`, plus YAML-provisioned silos. See [DATABASE_REFERENCE_CURRENT_STATE.md](DATABASE_REFERENCE_CURRENT_STATE.md) for full table inventory.
- **Global schemas:** `public`, `intelligence`, `pipeline` (and others per migrations)
- **Migrations:** `api/database/migrations/` — see `api/database/migrations/README.md`
- **Verification:** `PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py`

### Consolidated table inventory (non-exhaustive)

| Area | Tables |
|------|--------|
| **Domains** | `public.domains`, `public.domain_metadata`, `public.ml_processing_queue` |
| **Per-domain core** | `{schema}.articles`, `{schema}.storylines`, `{schema}.entity_index`, `{schema}.story_entity_index`, `{schema}.rss_feeds`, `{schema}.events`, `{schema}.tracked_events` |
| **Per-domain extensions** | Varies by silo — see each silo's migration; finance has `market_patterns`, `corporate_announcements`; legal may have domain-specific tables |
| **Intelligence core** | `intelligence.contexts`, `intelligence.entity_profiles`, `intelligence.versioned_facts`, `intelligence.content_refinement_queue` |
| **Intelligence longitudinal** | `intelligence.reference_events`, `intelligence.macro_series_observations`, `intelligence.sanctions_actions`, `intelligence.arc_definitions`, `intelligence.arc_reports` |
| **Intelligence cross-domain** | `intelligence.tracked_events`, `intelligence.graph_connection_links`, `intelligence.graph_connection_proposals` |
| **Automation** | `infrastructure.automation_run_history` |
| **Pipeline** | `pipeline_traces`, `pipeline_checkpoints`, `public.doc_index` |

---

## Connection pools

Four psycopg2 pools + SQLAlchemy (see `connection.py`):

| Pool | Purpose | Env vars | Checkout |
|------|---------|----------|----------|
| UI | Page loads, monitoring | `DB_POOL_UI_MIN/MAX` | Wait/retry default **12 s** (`DB_UI_GETCONN_TIMEOUT_SECONDS`) |
| Worker | Automation, batch | `DB_POOL_WORKER_MIN/MAX` | Wait/retry default **30 s** |
| Health | Health probes | `DB_POOL_HEALTH_MIN/MAX` | Short wait default **2 s** |
| SA | ORM services | `DB_POOL_SA_SIZE/OVERFLOW` | SQLAlchemy pool |

Rules:

1. Use `get_db_connection_context()` — always close connections.
2. Never hold connections across LLM calls, HTTP, or sleeps.
3. On exhaustion, checkout **waits/retries** then raises. `DB_ALLOW_DIRECT_FALLBACK` defaults **false**.
4. `get_db_pool_snapshot()` exposes `waiters` and `pressure=(in_use+waiters)/max`. AutomationManager defers *new* schedules when worker pressure is hot; it also publishes `public.db_pool_pressure_advisory` for PopOS workers (`POPOS_DB_PRESSURE_DEFER_ENABLED`).
5. Total pool max across all processes must stay under PostgreSQL `max_connections` / PgBouncer limits.

**Same code on Widow and PopOS:** deploy from this repo (PopOS `~/ni-popos-worker` → workspace symlink). Do not fork `connection.py` per host.

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
