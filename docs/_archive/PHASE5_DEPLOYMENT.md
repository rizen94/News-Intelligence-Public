# Phase 5: Deployment to Widow (Secondary)

## Summary

Phase 5 deploys the News Intelligence application to Widow (<WIDOW_HOST_IP>) as the secondary machine. Widow runs:

- **RSS collector** — Every 10 minutes (systemd worker)
- **Database backups** — Daily at 3 AM, weekly on Sundays at 4 AM (cron)
- **PostgreSQL** — Already running (Phase 2)

The primary machine keeps running the full stack (API, ML, Ollama, Redis, frontend) and connects to Widow's database.

## Prerequisites

- Phase 1–4 complete
- SSH to Widow (`ssh widow` or `ssh pete@<WIDOW_HOST_IP>`)
- `.db_password_widow` present in project root on primary

## Deploy

From the **primary** machine, in the project directory:

```bash
./scripts/deploy_to_widow.sh
```

This will:

1. Rsync code to `pete@<WIDOW_HOST_IP>:/opt/news-intelligence`
2. Copy `.db_password_widow` to Widow
3. Run `setup_widow_app.sh` on Widow (venv, pip, .env, systemd, cron)

## Manual Setup (if deploy script fails)

 SSH to Widow and run:

```bash
cd /opt/news-intelligence
./scripts/setup_widow_app.sh
```

Ensure `.env` has `DB_PASSWORD` set (from `.db_password_widow` or manual copy).

## Start the Secondary Worker (After Phase 6 Validation)

```bash
# On Widow
sudo systemctl start newsplatform-secondary
sudo systemctl status newsplatform-secondary
journalctl -u newsplatform-secondary -f
```

## Files Created

| File | Purpose |
|------|---------|
| `scripts/deploy_to_widow.sh` | Deploy from primary to Widow |
| `scripts/setup_widow_app.sh` | Setup venv, .env, systemd, cron (run on Widow) |
| `scripts/run_secondary_worker.py` | Daemon: RSS collection every 10 min |
| `scripts/db_backup.sh` | Daily `pg_dump` to NAS or local |
| `scripts/db_backup_weekly.sh` | Weekly compressed backup |
| `infrastructure/newsplatform-secondary.service` | Systemd unit |
| `infrastructure/newsplatform-backup.cron` | Backup cron |

## Backup Paths

- Primary: `/mnt/nas/backups` (if NFS mounted) or `/opt/news-intelligence/backups` (local fallback)
- Daily: `.../daily/` — kept 7 days
- Weekly: `.../weekly/` — kept 30 days

## Verify Before Phase 6

```bash
# On Widow
cd /opt/news-intelligence
source .venv/bin/activate
python api/collectors/rss_collector.py   # One-shot DB test
./scripts/db_backup.sh                   # Backup test
```
