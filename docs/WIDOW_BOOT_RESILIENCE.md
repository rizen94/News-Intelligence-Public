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
| Hardware RuntimeWatchdog | `/etc/systemd/system.conf.d/99-widow-runtime-watchdog.conf` (SP5100 `/dev/watchdog`, 60s) |
| Missed-nightly recovery | `widow-missed-nightly-recovery.timer` (01:15 + OnBootSec) |
| Disk IO governor | `widow-disk-io-governor.timer` (every 15s → `/run/.../disk_io_pressure.json` + DB) |
| API health watchdog | `widow-api-health-watchdog.timer` (every 2 min; recycle hung API) |
| API memory cgroup | `news-intelligence-api-public.service.d/memory.conf` (`MemoryHigh=4G`, `MemoryMax=5G`) |
| Gated daily apt | `/etc/cron.d/widow-daily-upgrade` (`03:30`; defers when disk hot) |
| journald USB caps | `/etc/systemd/journald.conf.d/99-widow-usb-root.conf` |

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

**Start-post readiness:** `ExecStartPost` runs `scripts/systemd_wait_readiness.sh` as **ignore-fail** (`-`) with a short budget (`NI_READINESS_ATTEMPTS`×`NI_READINESS_SLEEP_SEC`, default ~48s) via drop-in `service.d/nonblocking-readiness.conf`. Uvicorn is already listening under `Type=simple`; a long blocking start-post made restarts look like outages. Do **not** reintroduce a multi-minute blocking `ExecStartPost`.

---

## Post-reboot verification

```bash
/opt/news-intelligence/scripts/verify_widow_boot.sh
curl -s http://127.0.0.1:8000/api/system_monitoring/startup/readiness | jq .
journalctl -u news-intelligence-api-public --since "10 min ago" | grep BOOT_SUMMARY
```

**Ready** when readiness returns `"ready": true` (DB + automation thread alive + `is_running`).

---

## Overnight hard hang (incident 2026-09-26)

### What happened

| Fact | Evidence |
|------|----------|
| Previous boot ended **00:34:37** EDT | `journalctl --list-boots` boot −1 ends mid-topic-extraction; no shutdown/reboot log |
| **Not** the 00:45 graceful reboot | Last `widow-nightly-reboot.log` entry is **2026-09-25** 00:45; Sep 26 timer never fired (host already dead) |
| Marker left stale | `/var/tmp/widow-nightly-reboot.requested` mtime Sep 25 00:48 |
| Manual recovery | Boot **2026-09-26 07:28** (operator power-cycle ~morning) |
| Kernel silent | No oops/panic/OOM in last minutes of boot −1; journals simply stop (classic hard freeze) |
| Concurrent noise | Scheduler `RecursionError` on scale-up ticks; orchestrator `database is locked` — stress signals, not a clean reboot path |
| RuntimeWatchdog was off | `systemctl show RuntimeWatchdogSec` empty despite SP5100 `/dev/watchdog` present |

Nothing external touched the host. The machine **wedged**, so systemd never reached 00:45 and the heavy band (01:00–06:00) never ran.

### Root cause follow-up (2026-09-29)

Two separate mechanisms were confused as “Widow breaks every day”:

1. **Intentional 00:45 reboot** — `widow-nightly-reboot.timer` stopped the NI stack and rebooted every night. That looked like a daily outage to PopOS workers (`No route to host` until boot settled). **Disabled 2026-09-29** (`systemctl disable --now widow-nightly-reboot.timer`). Re-enable only if ops explicitly wants a maintenance reboot window.
2. **Scheduler infinite recursion** — `automation_should_defer_new_scheduled_work` was defined twice; the second definition called itself, producing thousands of `RecursionError` ticks/night (e.g. 2500+ on 2026-09-28) and stressing the host before any hang/reboot. **Fixed** by renaming the DB-pool check to `automation_db_pool_should_defer_phase` and having the combined gate call that + HTTP pressure.
3. **Hard hang / silent freeze** (Sep 26 class) — still mitigated by **RuntimeWatchdog** (`RuntimeWatchdogSec=60s`) + **missed-nightly recovery** (starts postgres/pgbouncer/nginx/API without requiring a reboot).

### Mitigations (installed by `setup_widow_boot_stack.sh`)

1. **Hardware RuntimeWatchdog** (`RuntimeWatchdogSec=60s`) — if the kernel stops petting `/dev/watchdog`, SP5100 forces a reboot within ~1–2 minutes instead of sitting dead until morning.
2. **Missed-nightly recovery** — on boot after 01:00 and daily at 01:15, if the nightly reboot marker is missing or older than 25h, start postgres/pgbouncer/nginx/API/RSS and refresh the marker so a skipped 00:45 does not leave the stack down for the heavy window.
3. **Scheduler defer gate** — no self-recursive `automation_should_defer_new_scheduled_work` (deployed 2026-09-29).
4. **Disk IO write governor** (2026-09-30) — see [USB root disk IO governor](#usb-root-disk-io-governor) below.
5. **API health watchdog** (2026-10-01) — see [API health watchdog](#api-health-watchdog) below. Recycles hung uvicorn without host reboot.
6. **API MemoryHigh=4G** — cgroup soft limit raised from 3G (overnight reclaim thrash); hard `MemoryMax=5G` unchanged.

Verify:

```bash
systemctl show -p RuntimeWatchdogSec -p WatchdogDevice
# expect RuntimeWatchdogSec=1min (or 60s), WatchdogDevice=/dev/watchdog
systemctl is-enabled widow-nightly-reboot.timer   # should be disabled
systemctl list-timers widow-missed-nightly-recovery.timer
systemctl list-timers widow-api-health-watchdog.timer
systemctl show news-intelligence-api-public -p MemoryHigh -p MemoryMax
# expect MemoryHigh=4G MemoryMax=5G
sudo journalctl -u widow-missed-nightly-recovery -n 30
# RecursionError should be gone:
journalctl -u news-intelligence-api-public --since "1 hour ago" | grep -c RecursionError
```

### Operator notes

- After a **watchdog** reboot shortly before 00:45, graceful reboot may **ABORT** (uptime &lt; 30 min). That is intentional (anti boot-loop); the host is already up for heavy — recovery timer only acts if the marker stays stale.
- Prefer **not** re-enabling `widow-nightly-reboot.timer` unless there is a documented maintenance need; keep `Persistent=false` if it is ever re-enabled so a midday manual reboot does not instantly re-trigger a reboot.

---

## USB root disk IO governor

Widow’s OS root is a **Toshiba USB HDD** (`/dev/sdc`). Concurrent apt + Postgres writes aborted the ext4 journal (2026-09-30). Until root can move off USB, write timing is gated.

### Signal

| Path | Role |
|------|------|
| `/run/news-intelligence/disk_io_pressure.json` | tmpfs snapshot for apt (works even if API/DB is down) |
| `public.disk_io_pressure_advisory` | DB row for AutomationManager / Monitor (`resource_router.disk_io_pressure`) |
| `widow-disk-io-governor.timer` | Samples every **15s** |

**Default defer when** (env-tunable):

| Gate | Condition |
|------|-----------|
| `defer_heavy_writes` (apt) | util ≥ **85%** over the hot window **or** write ≥ **8 MB/s** |
| `defer_new_work` (automation) | write ≥ **8 MB/s**, **or** util ≥ 85% **and** write ≥ **2 MB/s**, **or** util ≥ **95%** (USB saturation) |

Mild util-hot / low-write spikes gate apt only. Automation defers on write floor **or** saturation (≥95% util), so a pegged USB disk still sheds load. AutomationManager reads **`defer_new_work` only** (not heavy). Stale samples (&gt;120s) **fail-open**. Hot window default **45s** (15s timer keeps multiple samples).

| Env | Default | Meaning |
|-----|---------|---------|
| `DISK_IO_UTIL_DEFER_THRESHOLD` | `85` | util % (hot_util / apt) |
| `DISK_IO_SATURATION_UTIL_THRESHOLD` | `95` | util % → automation defer even at low KB/s |
| `DISK_IO_WRITE_KB_S_DEFER_THRESHOLD` | `8192` | KB/s (~8 MB/s) heavy / apt |
| `DISK_IO_AUTOMATION_WRITE_FLOOR_KB_S` | `2048` | KB/s floor with hot util for automation |
| `DISK_IO_HOT_WINDOW_SEC` | `45` | util averaging window |
| `DISK_IO_GOVERNOR_DEVICE` | auto (`sdc`) | override device name |
| `AUTOMATION_DISK_IO_PRESSURE_GATE_ENABLED` | `true` | OR into schedule defer gate |

### Consumers

1. **`widow-daily-upgrade.sh` (03:30 cron)** — `nice`/`ionice`, flock, skip+`systemd-run --on-active=30min` when `defer_heavy_writes` (max 6 defers/day). Force with `WIDOW_DISK_IO_FORCE=1`.
2. **AutomationManager** — `automation_should_defer_new_scheduled_work` also checks disk pressure (same exempts: `health_check`, `pending_db_flush`).
3. **`newsplatform-secondary`** — `run_secondary_worker.py` skips RSS when `/run` says `defer_new_work` (`RSS skipped (disk IO pressure)`).
4. **`apt-daily-upgrade.timer`** — disabled by boot-stack setup (ungated Debian upgrade races our script).

### Ops checks

```bash
systemctl list-timers widow-disk-io-governor.timer
cat /run/news-intelligence/disk_io_pressure.json
sudo -u postgres psql -d news_intel -c 'TABLE public.disk_io_pressure_advisory'
# Force apt despite pressure:
sudo WIDOW_DISK_IO_FORCE=1 /usr/local/sbin/widow-daily-upgrade.sh
```

---

## API health watchdog

Hung uvicorn (health curl timeout while systemd still `active`) under USB/DB load — Oct 1 morning class.

| Unit | Role |
|------|------|
| `widow-api-health-watchdog.timer` | Every **2 min** (`OnBootSec=3min`) |
| `widow_api_health_watchdog.sh` | `/usr/local/sbin/…` — 5s health probe |

**Recovery** after **2** consecutive failures: stop secondary → restart API (SIGKILL escalate if needed) → wait health 200 → start secondary. **30 min** cooldown in `/run/news-intelligence/api_health_watchdog_cooldown`. Log: `/var/log/news-intelligence/api-health-watchdog.log`.

Manual drill (same as watchdog):

```bash
sudo systemctl stop newsplatform-secondary
sudo systemctl restart news-intelligence-api-public
# if wedged: sudo systemctl kill -s SIGKILL news-intelligence-api-public && sudo systemctl start news-intelligence-api-public
curl -m 5 -sS http://127.0.0.1:8000/api/system_monitoring/health
sudo systemctl start newsplatform-secondary
```

**Memory:** `MemoryHigh=4G` / `MemoryMax=5G` via `news-intelligence-api-public.service.d/memory.conf` (installed by boot stack).

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
| Host dead overnight / skipped 00:45 | `journalctl --list-boots`; marker age on `/var/tmp/widow-nightly-reboot.requested`; confirm `RuntimeWatchdogSec`; `journalctl -u widow-missed-nightly-recovery` |

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
