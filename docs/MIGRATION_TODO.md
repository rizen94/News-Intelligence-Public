# Migration — Three-Machine Architecture

**Status:** ✅ Phases 1–7 complete (March 2026)

---

## Completed Phases

| Phase | Description |
|-------|--------------|
| Pre | Archive, config audit, migration plan, infrastructure |
| 1 | Secondary discovery (Widow 192.168.93.101) |
| 2 | PostgreSQL 16 on Widow |
| 3 | Database migration NAS → Widow |
| 4 | Application code (Widow default, NAS rollback) |
| 5 | Deploy to Widow (RSS worker, backups, systemd, cron) |
| 6 | Integration validation |
| 7 | Go live, NAS PostgreSQL decommissioned |

---

## Remaining

- [ ] Phase 8: Monitoring and maintenance
- [ ] Optional: NFS on Widow for backups → NAS

---

## Rollback

- **To NAS:** Set `.env` to `DB_HOST=localhost`, `DB_PORT=5433`, `DB_NAME=news_intelligence`; run `setup_nas_ssh_tunnel.sh`; restart PostgreSQL on NAS; restart app.
- **Tag:** `pre-migration-rollback`
