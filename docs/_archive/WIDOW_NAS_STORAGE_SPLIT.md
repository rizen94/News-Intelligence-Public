# Widow + NAS: Processing on Widow, Storage on NAS

Use **Widow** for the database and all processing; use the **NAS** for backups, log archives, and optional cold data so Widow’s disk stays small.

---

## Overview

| Role | Widow (192.168.93.101) | NAS (192.168.93.100) |
|------|------------------------|------------------------|
| **Database** | PostgreSQL (live, all queries) | — |
| **Processing** | API, RSS collector, cron jobs | — |
| **Backups** | pg_dump runs here; **writes to NAS** | `/backups/daily`, `/backups/weekly` |
| **Log files** | Recent logs only (after archive) | Long-term `logs/` archive |
| **Cold data** | Optional: export then prune | Exported dumps / CSVs |

Widow mounts the NAS (e.g. at `/mnt/nas`). Backups and archive scripts write to that mount so data lives on NAS, not on Widow’s drive.

---

## 1. Mount NAS on Widow

Backups and archives go to NAS only if Widow has the NAS mounted. Do this **on Widow**.

### Option A: NFS (if your NAS exports NFS)

```bash
# On Widow
sudo mkdir -p /mnt/nas
# Add to /etc/fstab (adjust share path to your NAS):
# 192.168.93.100:/share/news-platform  /mnt/nas  nfs  defaults,soft,timeo=150,retrans=3,_netdev  0  0
sudo mount -a
```

### Option B: SMB/CIFS

```bash
# On Widow
sudo mkdir -p /mnt/nas
sudo apt-get install -y cifs-utils
# Create credentials file (optional, for password auth):
# echo "username=YourNASUser" | sudo tee /etc/nas-credentials
# echo "password=YourNASPass" | sudo tee -a /etc/nas-credentials
# sudo chmod 600 /etc/nas-credentials
# Add to /etc/fstab:
# //192.168.93.100/share-name  /mnt/nas  cifs  credentials=/etc/nas-credentials,uid=$(id -u),gid=$(id -g),iocharset=utf8,_netdev  0  0
sudo mount -a
```

### Layout under the mount

Create (on NAS or via mount) a consistent layout:

```text
/mnt/nas/
  news-intelligence/
    backups/
      daily/
      weekly/
    logs/           # Archived log files from Widow
    cold-export/    # Optional: old data exported by date
```

Then set (or leave default) in backup scripts:

- `BACKUP_BASE=/mnt/nas/news-intelligence/backups`  
  or keep existing default `/mnt/nas/backups` if you use that.

---

## 2. Backups: already wired for NAS

- **Daily:** `scripts/db_backup.sh` (cron on Widow, e.g. 3 AM)  
  - Writes to `$BACKUP_BASE/daily` (default `/mnt/nas/backups/daily`; fallback `/opt/news-intelligence/backups/daily`).
- **Weekly:** `scripts/db_backup_weekly.sh` (e.g. Sunday 4 AM)  
  - Writes to `$BACKUP_BASE/weekly`.

If `/mnt/nas` is mounted and `BACKUP_BASE` is `/mnt/nas/backups` (or `/mnt/nas/news-intelligence/backups`), backups use NAS and Widow’s disk stays clear. No code change needed; just ensure the mount exists before cron runs.

---

## 3. Log files: archive to NAS and trim Widow

So that `logs/` on Widow doesn’t grow forever:

- Use **`scripts/archive_logs_to_nas.sh`** (run from Widow or from a machine that has both project `logs/` and NAS mount).

It:

- Copies `logs/*.jsonl` (and optionally other log files) to the NAS (e.g. `$NAS_LOG_ARCHIVE`).
- Truncates or rotates the local files so Widow keeps only recent data.

Schedule it on Widow (e.g. daily after backup):

```bash
# Example cron (Widow): archive logs to NAS at 5 AM
0 5 * * * /opt/news-intelligence/scripts/archive_logs_to_nas.sh >> /opt/news-intelligence/logs/archive_logs.log 2>&1
```

---

## 4. Optional: cold data export to NAS

To free even more space on Widow, you can **export** old data to NAS and then optionally **prune** it from the live DB.

- **`scripts/export_cold_data_to_nas.sh`** (optional):  
  - Exports old rows (e.g. articles, contexts, events older than N days) to the NAS (`cold-export/` or similar) via `pg_dump` or `COPY`.
  - Does **not** delete from Widow by default; you can add a separate, careful prune step after verifying exports.

This is optional and for advanced use; backups + log archival are usually enough to keep Widow’s drive under control.

---

## 5. Summary checklist

| Step | Action |
|------|--------|
| 1 | Mount NAS on Widow at `/mnt/nas` (NFS or CIFS). |
| 2 | Create `.../backups/daily`, `.../backups/weekly` (and optionally `.../logs`, `.../cold-export`) under that mount. |
| 3 | Keep `BACKUP_BASE` default or set to `/mnt/nas/backups` (or `/mnt/nas/news-intelligence/backups`). Existing backup cron on Widow will then store on NAS. |
| 4 | Install and schedule `archive_logs_to_nas.sh` on Widow so log files are moved to NAS and local copies trimmed. |
| 5 | (Optional) Use `export_cold_data_to_nas.sh` and, if desired, a separate prune process. |

Result: **Widow** = DB + processing (small, fast disk); **NAS** = backups, log archives, and optional cold exports (large storage).
