# Release v4.1 — Widow Migration (2026-03-01)

## Summary

Database moved from NAS to Widow (secondary machine). NAS is now storage-only. Three-machine architecture is live.

---

## What Was Accomplished

### Phases Completed

| Phase | Description |
|-------|-------------|
| 1 | Secondary discovery — Widow (<WIDOW_HOST_IP>), SSH, specs |
| 2 | PostgreSQL 16 on Widow |
| 3 | DB migration from NAS (146 tables, ~335 total) |
| 4 | App code — Widow as default DB, NAS rollback support |
| 5 | Deploy to Widow — RSS worker, backups, systemd, cron |
| 6 | Integration validation |
| 7 | Go live, NAS PostgreSQL decommissioned |

### New Features

- **Secondary RSS worker** — Runs on Widow, collects RSS every 10 min
- **DB backups** — Daily 03:00, weekly Sunday 04:00 on Widow
- **Multi-machine startup** — `start_system.sh` supports Widow and NAS rollback
- **Widow no-sleep** — Script to keep Widow from sleeping

### New Scripts

- `scripts/deploy_to_widow.sh` — Deploy from primary to Widow
- `scripts/setup_widow_app.sh` — Setup on Widow (venv, .env, systemd)
- `scripts/run_secondary_worker.py` — RSS daemon
- `scripts/db_backup.sh` / `scripts/db_backup_weekly.sh` — Backup scripts
- `scripts/configure_widow_no_sleep.sh` — Disable Widow suspend
- `scripts/decommission_nas_postgresql.sh` — Stop NAS PostgreSQL

### Infrastructure

- `infrastructure/newsplatform-secondary.service` — Systemd unit for RSS worker
- `infrastructure/newsplatform-backup.cron` — Backup cron template
- `infrastructure/secondary-machine-info.txt` — Widow specs
- `infrastructure/migration-state.json` — Migration state

---

## Breaking Changes

- **NAS PostgreSQL** — Stopped and disabled. NAS is storage-only.
- **DB connection** — Default is Widow (<WIDOW_HOST_IP>:5432, `news_intel`).
- **SSH tunnel** — No longer required for normal operation (only for NAS rollback).

---

## Rollback

To revert to NAS database:

1. Start PostgreSQL on NAS
2. In `.env`: `DB_HOST=localhost`, `DB_PORT=5433`, `DB_NAME=news_intelligence`
3. Run `./scripts/setup_nas_ssh_tunnel.sh`
4. Restart app

Tag: `pre-migration-rollback`

---

## Remaining (Phase 8)

- Monitoring and maintenance
- Optional: NFS mount for backups on Widow → NAS
