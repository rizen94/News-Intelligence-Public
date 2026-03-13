# NAS — Legacy & Storage

**NAS (192.168.93.100)** is now **storage-only**. PostgreSQL was migrated to Widow in v5.0.

---

## Rollback to NAS Database

See [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md#rollback) for rollback steps.

---

## Storage (NFS/SMB)

If using NAS for backups/archives, typical mounts:

- `/share/news-platform/backups`
- `/share/news-platform/archives`
- `/share/news-platform/logs`

SSH: `ssh -p 9222 Admin@192.168.93.100` (credentials in secure location).
