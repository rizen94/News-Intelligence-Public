**Status:** Superseded — historical **2025-02-21** migration-prep snapshot. Current architecture: [ARCHITECTURE_AND_OPERATIONS.md](../../ARCHITECTURE_AND_OPERATIONS.md), [DATABASE.md](../../DATABASE.md).

---

# Phase 4.1 Config Audit — Migration Prep

**Date:** 2025-02-21  
**Purpose:** Document current config structure for three-machine migration.

## Config Files Found

- `.env` (root), `configs/.env`
- `api/config/finance_schedule.yaml`, `api/config/sources.yaml`
- `docker-compose.yml`, `pyproject.toml`
- `monitoring/prometheus.yml`

## DB Connection Points

Primary: `api/shared/database/connection.py` — `get_db_connection()`, `get_db_config()`
Uses env: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
Current: SSH tunnel localhost:5433 → NAS <NAS_HOST_IP>:5432

## NAS (<NAS_HOST_IP>) References in App Code

| File | Purpose |
|------|---------|
| `api/main.py` | SSH tunnel pgrep check, tunnel verification |
| `api/shared/database/connection.py` | Tunnel docs, blocking direct NAS |
| `api/collectors/rss_collector.py` | Fallback DB_HOST default |
| `api/scripts/add_official_feeds.py` | Default DB_HOST |
| `api/scripts/analyze_existing_articles.py` | Default DB_HOST |
| `.env` | NAS_HOST |
| `scripts/archive/nas_migration/*` | Legacy migration scripts |

## Migration Change Summary

1. DB_HOST will change from `localhost` (tunnel) to SECONDARY_IP (direct)
2. SSH tunnel to NAS will be removed for DB; NAS used only for storage mounts
3. Connection code in `api/shared/database/connection.py` needs role-aware config
