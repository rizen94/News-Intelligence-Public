# Widow Boot Resilience — Operator Runbook

**Purpose:** Single checklist for making News Intelligence survive reboots on **Widow** (`192.168.93.101`).

**Related:** [PIPELINE_OPERATIONS_WIDOW.md](PIPELINE_OPERATIONS_WIDOW.md) · [WIDOW_DB_ADJACENT_CRON.md](WIDOW_DB_ADJACENT_CRON.md) · [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md)

---

## Boot order

```text
network-online
  → postgresql.service
  → pgbouncer.service          (DB_PORT=6432 in .env)
  → ollama.service             (local GTX 1080, :11434)
  → nginx.service              (public demo SPA + /api proxy)
  → news-intelligence-api-public.service   (single uvicorn + AutomationManager)
  → newsplatform-secondary.service         (RSS every ~10 min)
  → cron (systemd)             → db-adjacent, backups, log archive
```

Optional: `mnt-nas.mount` before backup cron — see [infrastructure/mnt-nas.mount.example](../infrastructure/mnt-nas.mount.example).

---

## One-time install

Run on Widow from production tree:

```bash
cd /opt/news-intelligence
./scripts/setup_widow_boot_stack.sh
```

This installs:

| Component | systemd / cron |
|-----------|----------------|
| API + AutomationManager | `news-intelligence-api-public.service` |
| RSS worker | `newsplatform-secondary.service` |
| Meta-target | `news-intelligence.target` |
| Boot verify (optional) | `news-intelligence-boot-check.service` |
| DB-adjacent sync | `/etc/cron.d/news-intelligence-widow-db` (`*/15`) |
| Daily DB backup | `/etc/cron.d/newsplatform-backup` (`03:00`) |
| Log archive | `/etc/cron.d/news-intelligence-log-archive` (`05:00`) |
| Weekly retained backup | `/etc/cron.d/news-intelligence-weekly-backup` (Sun `04:30`) |

Enable and start:

```bash
sudo fuser -k 8000/tcp 2>/dev/null || true   # stop manual nohup if present
sudo systemctl enable --now news-intelligence.target
```

---

## Required `.env` (production)

Path: `/opt/news-intelligence/.env`

```bash
AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE=true
AUTOMATION_DISABLED_SCHEDULES=context_sync,entity_profile_sync,pending_db_flush
AUTOMATION_MAX_CONCURRENT_TASKS=6
MAX_CONCURRENT_OLLAMA_TASKS=3
DB_HOST=127.0.0.1
DB_PORT=6432
OLLAMA_HOST=http://localhost:11434
OLLAMA_POP_OS_HOST=http://192.168.93.99:11434
```

After `.env` changes:

```bash
sudo systemctl restart news-intelligence-api-public
# or: ./scripts/restart_api_with_db.sh  (delegates to systemd when enabled)
```

---

## Post-reboot verification

```bash
/opt/news-intelligence/scripts/verify_widow_boot.sh
curl -s http://127.0.0.1:8000/api/system_monitoring/startup/readiness | jq .
journalctl -u news-intelligence-api-public --since "10 min ago" | grep BOOT_SUMMARY
```

**Ready** when readiness returns `"ready": true` (DB + automation thread alive + `is_running`).

---

## API endpoints (startup / ops)

| Endpoint | Use |
|----------|-----|
| `GET /api/system_monitoring/startup/readiness` | systemd `ExecStartPost`, boot verify (200=ready, 503=warming up) |
| `GET /api/system_monitoring/automation/status` | workers, `startup_ready`, `pipeline_schedule`, `disabled_schedules` |
| `POST /api/system_monitoring/monitoring/trigger_phase` | manual phase (409 if phase is cron-disabled) |

---

## Do NOT use on production Widow

| Path | Why |
|------|-----|
| `start_system.sh` | Spawns a **second** AutomationManager alongside the API |
| `restart_api_with_db_manual.sh` | nohup uvicorn — use systemd instead |
| `news-intelligence-widow.service` with `--workers 4` | Multiple AutomationManagers (dev unit is single-worker only) |

---

## External dependencies (degraded, not blocking)

| Dependency | Host | If down |
|------------|------|---------|
| PopOS Ollama 70B | `192.168.93.99:11434` | Narrative finisher degraded; local 8B still runs |
| PopOS Caddy | WAN `:443` | Public URL down; LAN API still works |
| NAS `/mnt/nas` | CIFS mount | Backups/log archive skip gracefully |

PopOS: `systemctl enable --now ollama` and `ollama pull llama3.1:70b`.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| API not up after reboot | `systemctl status news-intelligence-api-public`; `journalctl -u news-intelligence-api-public -n 80` |
| Readiness 503 | Wait ~60s for automation preflight; check PgBouncer + postgres |
| Automation thread died | Readiness shows `automation_thread_alive: false`; restart API unit |
| trigger_phase 409 | Phase in `AUTOMATION_DISABLED_SCHEDULES` — use cron / `run_widow_db_adjacent.py` |
| Duplicate automation | `pgrep -af uvicorn` — must be **one** listener on `:8000` |

---

## Deploy code updates

```bash
# From dev machine (rsync dev → prod on Widow)
rsync -av --exclude=.venv --exclude=node_modules \
  "/home/pete/Documents/projects/News Intelligence/api/" \
  widow:/opt/news-intelligence/api/
rsync -av "/home/pete/Documents/projects/News Intelligence/scripts/" \
  widow:/opt/news-intelligence/scripts/
sudo systemctl restart news-intelligence-api-public
```

Apply DB migrations as usual under `api/database/migrations/`.

---

## Success criteria (controlled reboot)

- All systemd units active within ~3 minutes
- `startup/readiness` → `"ready": true`
- `automation/status` → workers ≤ `AUTOMATION_MAX_CONCURRENT_TASKS`
- Single uvicorn on `:8000`
- Public URL returns 200 when PopOS Caddy + Widow nginx are up
