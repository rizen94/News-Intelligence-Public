# PgBouncer and connection budget

PostgreSQL has a hard **`max_connections`** ceiling. Many application pools (each holding idle sessions), multiple hosts (Widow API, desktop dev, cron), and a small `max_connections` (e.g. 60) combine into “remaining slots reserved for superuser” errors. **PgBouncer** sits between apps and Postgres and multiplexes many **client** connections onto fewer **server** connections (especially in **transaction** pooling mode).

This doc aligns with the project priority: **frontend and monitoring stay responsive first**; **automation keeps moving** second. Tuning is iterative: use `pg_stat_activity` (and PgBouncer `SHOW POOLS` / `SHOW STATS`) to rebalance after you observe real load.

---

## Roles

| Layer | Role |
|-------|------|
| **PgBouncer** | Caps how many sessions hit Postgres; queues or rejects at the pooler when the server budget is exhausted. Prefer **transaction pooling** for stateless request/transaction patterns (typical API + short automation steps). |
| **App UI pool** (`get_ui_db_connection*`, `DomainAwareService.get_read_db_connection`) | Reserved for page loads, monitoring, and hot read paths (e.g. article listings); **3 s** checkout so the browser does not hang when the worker pool is busy with automation. |
| **App worker pool** (`get_db_connection*`) | Automation, RSS, enrichment, batch paths; **30 s** checkout timeout. |
| **SQLAlchemy pool** | ORM services only; separate budget. |
| **Ephemeral connections** | Infrequent jobs (briefing, digest, narrative finisher) open a short-lived session and **fully disconnect**—they still count against PgBouncer/Postgres **while active**. |

---

## Recommended topology

```
[Browser / API clients]
        → FastAPI (one or more processes)
              → psycopg2 UI pool  ──┐
              → psycopg2 worker pool ─┼→ PgBouncer :6432 (or similar)
              → SQLAlchemy pool   ──┘         → PostgreSQL :5432
[Widow cron / scripts] ───────────────────────→ (same PgBouncer DSN)
```

- Point **`DB_HOST` / `DB_PORT`** at **PgBouncer**, not Postgres, for routine app and cron traffic.
- Keep **admin / migrations** connecting **directly** to Postgres (or a separate PgBouncer database entry with session pooling) when you need prepared statements across transactions or long sessions.

---

## PgBouncer (outline)

Exact file paths depend on the OS (Debian: often `/etc/pgbouncer/pgbouncer.ini`). Illustrative settings:

```ini
[databases]
news_intel = host=127.0.0.1 port=5432 dbname=news_intel

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
pool_mode = transaction
default_pool_size = 15
reserve_pool_size = 4
max_client_conn = 200
```

- **`pool_mode = transaction`**: server connection returned after each transaction; best fit for most API and automation **short** transactions. Avoid long transactions and session-level features that break with pooling (some `SET`, `LISTEN`, temp tables per session).
- **`default_pool_size`**: real backends to Postgres **per user+database** (roughly). Size from your **Postgres budget**, not from app pool maxes summed blindly.
- **`max_client_conn`**: how many app-side sockets PgBouncer accepts; can be larger than Postgres `max_connections` because of multiplexing.

Match **`auth_type`** and user passwords to PostgreSQL (`newsapp` etc.). Reload PgBouncer after changes.

**App `.env` example (via pooler):**

```env
DB_HOST=<WIDOW_OR_POOLER_LAN_IP>
DB_PORT=6432
DB_NAME=news_intel
DB_USER=newsapp
DB_PASSWORD=...
# Optional documentation-only: set to pgbouncer when DB_PORT=6432 (for runbooks / validation scripts)
# NEWS_INTEL_PGBOUNCER_TARGET=pgbouncer
```

There is no separate `PGBOUNCER_ENABLED` code path — routing is entirely `DB_HOST` + `DB_PORT`.

---

## Connection budget worksheet

Work in **max concurrent server backends** (Postgres or PgBouncer→Postgres), not “number of app pool slots” alone.

1. **`SHOW max_connections;`** and **`SHOW superuser_reserved_connections;`** on Postgres. Effective ceiling for normal roles:  
   `max_connections - superuser_reserved_connections` (approximate guardrail).

2. **Subtract** direct connections: replication, admin, one-off `psql`, other services **bypassing** PgBouncer.

3. **PgBouncer → Postgres:** set **`default_pool_size`** (and related) so total backends used by the pooler stays inside what remains.

4. **Per application process** (each uvicorn worker counts separately):

   - **UI pool max** + **worker pool max** + **SA size + SA overflow** = worst-case **client** connections from that process to PgBouncer.
   - With transaction pooling, many idle app slots do **not** map 1:1 to Postgres backends; under load, concurrent **active** transactions drive server use.

5. **Priority rule (this project):**

   - Prefer **enough UI cap** that monitoring and main UI routes rarely wait on the worker pool (they already use `get_ui_db_connection*` where wired).
   - Size **worker max** for sustained automation **without** starving the UI pool on the same host; if automation backs up, increase worker max **only after** PgBouncer/Postgres headroom allows it, or scale workers / split processes.

6. **Observe and rebalance:**

   - Postgres: `pg_stat_activity` counts by `application_name`, `state`, `usename`.
   - PgBouncer: `SHOW POOLS;`, `SHOW STATS;`, `SHOW CLIENTS;`.
   - App: automation queue depth, `GET /api/system_monitoring/automation/status`, API latency.

Defaults in `shared.database.connection` are **conservative** for small Postgres `max_connections`; raise **`DB_POOL_WORKER_MAX`** (and PgBouncer pool size) when metrics show headroom and backlog.

---

## Env vars (quick reference)

| Variable | Purpose |
|----------|---------|
| `DB_HOST`, `DB_PORT` | Set to PgBouncer when deployed. |
| `DB_POOL_UI_MIN` / `DB_POOL_UI_MAX` | UI/monitoring psycopg2 pool. |
| `DB_POOL_WORKER_MIN` / `DB_POOL_WORKER_MAX` | Worker psycopg2 pool. |
| `DB_POOL_SA_SIZE` / `DB_POOL_SA_OVERFLOW` | SQLAlchemy. |
| `DB_UI_GETCONN_TIMEOUT_SECONDS` | Default **3** — fail fast for UI. |
| `DB_WORKER_GETCONN_TIMEOUT_SECONDS` | Default **30** — automation can wait slightly longer. |

Legacy **`DB_POOL_MIN` / `DB_POOL_MAX`** still map to worker min/max when the worker-specific vars are unset (see `connection.py`).

---

## Install on Widow (Debian)

- Template: `configs/pgbouncer/pgbouncer.ini.example`
- **Script (run on Widow as root):** `scripts/install_pgbouncer_widow.sh` — installs the package, writes `userlist.txt` from `pg_authid` (SCRAM) for `newsapp`, sets `ALTER ROLE newsapp SET statement_timeout` (default 120000 ms, override with `STATEMENT_TIMEOUT_MS`), enables `pgbouncer.service`.
- After install: set **`DB_PORT=6432`** and pool env vars in `/opt/news-intelligence/.env`, then restart `news-intelligence-api-public` and `newsplatform-secondary`.

## Related docs

- `AGENTS.md` — database rules and pool env vars.
- `docs/CODING_STYLE_GUIDE.md` — connection pool architecture table.
- `docs/TROUBLESHOOTING.md` — pool exhaustion and timeouts.
