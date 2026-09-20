# Secrets and settings index (News Intelligence)

**Paths only — no live passwords.**

NI env authority is on **Widow** (`configs/.env`, `.db_password_widow`). Cross-project settings (Homelab Postgres MCP, shared Ollama) are documented in the Homelab canonical index.

**Full cross-project index:** [../../HomeLab-AI-Stack/docs/SECRETS_AND_SETTINGS_INDEX.md](../../HomeLab-AI-Stack/docs/SECRETS_AND_SETTINGS_INDEX.md)

---

## NI authoritative files (Widow)

| Path | Purpose |
|------|---------|
| `configs/.env` | `DB_*`, API keys, Ollama routing |
| `.env` | Project-root overrides |
| `.db_password_widow` | DB password file fallback |

---

## NI database env vars

| Variable | Typical value (Widow) |
|----------|----------------------|
| `DB_HOST` | `localhost` or `192.168.93.101` |
| `DB_PORT` | **`6432`** (PgBouncer) for API/workers; use **`5432`** for migrations and one-off admin scripts |
| `DB_MAINTENANCE_PORT` | Optional; forces direct Postgres port for maintenance scripts when `DB_PORT=6432` |
| `DB_NAME` | `news_intel` |
| `DB_USER` | `newsapp` |
| `DB_PASSWORD` | In `.env` or `.db_password_widow` |

Homelab reads the same database via `NEWS_INTEL_DATABASE_URI` (read-only MCP).

---

## Related

- [DATABASE.md](DATABASE.md)
- [../../PROJECT_BOUNDARIES.md](../../PROJECT_BOUNDARIES.md)
- [../PROJECT_STATUS.md](../PROJECT_STATUS.md)
