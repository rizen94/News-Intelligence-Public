# Database backup (homelab)

## Policy

| Item | Choice |
|------|--------|
| **Goal** | One cold copy on the NAS, minimal wasted space |
| **Method** | Nightly `pg_dump` **custom format** (`-F custom`), **single file** replaced each run |
| **File** | `news_intel_latest.pgdump` |
| **RPO** | ~24 hours if cron runs daily (work committed *after* the dump started is not in the file) |
| **Retention** | **No** stack of dated dumps; optional local fallback on Widow only if NAS unavailable |

This is **not** WAL archiving or point-in-time recovery—appropriate for a home server.

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
