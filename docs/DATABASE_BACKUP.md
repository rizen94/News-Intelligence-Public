# Database backup (homelab)

## Policy (Phase 0 — longitudinal intelligence)

| Tier | Cadence | Retention | Location |
|------|---------|-----------|----------|
| **Hot rolling** | Daily (03:00) | Single latest file replaced each run | NAS `news_intel_latest.pgdump` |
| **Weekly local** | Sunday | Keep **4** weekly files on separate disk | `BACKUP_WEEKLY_DIR` (default: `/opt/news-intelligence/backups/weekly`) |
| **Monthly cold** | 1st of month | **12** months then prune | NAS `database-backup/monthly/` or off-site copy |

**RPO:** ~24h for daily hot copy; weekly/monthly are disaster-recovery anchors.  
**Not** WAL/PITR — appropriate for homelab; living corpus is irreplaceable once longitudinal facts accumulate.

## Daily single-file (existing)

| Item | Choice |
|------|--------|
| **Method** | Nightly `pg_dump` **custom format** (`-F custom`), **single file** replaced each run |
| **File** | `news_intel_latest.pgdump` |
| **Script** | [`scripts/db_backup_single_latest.sh`](../scripts/db_backup_single_latest.sh) |

## Weekly archive

Use [`scripts/db_backup_weekly_retained.sh`](../scripts/db_backup_weekly_retained.sh) (Sunday cron):

```bash
# Example crontab (Widow, Sunday 04:00 ET)
0 4 * * 0 pete /opt/news-intelligence/scripts/db_backup_weekly_retained.sh >> /opt/news-intelligence/logs/backup-weekly.log 2>&1
```

Env: `BACKUP_WEEKLY_DIR`, `BACKUP_WEEKLY_KEEP=4`

## Monthly cold archive

On the 1st of each month, copy the latest weekly (or run dedicated dump) to:

`$NAS_BACKUP_PATH/monthly/news_intel_YYYY-MM.pgdump`

Prune monthly files older than 12 months. Copy to off-site cold storage with:

[`scripts/db_backup_cold_archive.sh`](../scripts/db_backup_cold_archive.sh) (`BACKUP_COLD_DIR` or `NAS_BACKUP_PATH/database-backup/cold`).

## Restore (outline)

## NAS location

On hosts where the share is mounted (typical Linux path):

- **SMB:** `smb://192.168.93.100/public/Data Lake Storage/...`
- **Filesystem:** `/mnt/nas/Data Lake Storage/news-intelligence/database-backup/`

Override with `BACKUP_BASE` if your mount differs.

## Script

- **`scripts/db_backup_single_latest.sh`** — writes `news_intel_latest.pgdump` under `BACKUP_BASE`, using a temp file then `mv` for atomic replace.
- Loads **`../.env`** when present so `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` match the app.
- **`configs/env.example`** documents `NAS_BACKUP_PATH` / related vars for reference; the script default path matches the Data Lake layout above.

## Scheduling

- **Template:** `infrastructure/newsplatform-backup.cron` — single daily job (03:00) calling `db_backup_single_latest.sh`.
- **Older scripts** `db_backup.sh` / `db_backup_weekly.sh` kept for reference; they retain **multiple** files—do **not** run alongside this policy if you want only one NAS copy.

## Restore (outline)

1. Create an empty database (or drop objects in a scratch DB).
2. `pg_restore --no-owner --role=... -d news_intel path/to/news_intel_latest.pgdump`  
   (Exact flags depend on ownership and extensions—test on a non-prod DB first.)

## First-time checklist

- [ ] CIFS mount active (`/mnt/nas/Data Lake Storage` reachable).
- [ ] `.env` credentials allow `pg_dump` (same as app DB user).
- [ ] Cron on the machine that can reach PostgreSQL **and** the NAS (usually Widow for DB on Widow; or Primary with `DB_HOST` pointing at Widow).

## Related automation (different purpose)

The **`data_cleanup`** phase in `automation_manager` can delete **old articles by age** (`_execute_data_cleanup`). That is **not** this backup policy—keep that phase disabled or reviewed separately so it does not fight with your NAS retention goals.

---

**See also:** [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) · [DB_PRODUCTION_MAINTENANCE_RUNBOOK.md](DB_PRODUCTION_MAINTENANCE_RUNBOOK.md)
