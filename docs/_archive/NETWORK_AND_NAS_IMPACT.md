# Network Traffic & NAS Impact

**TL;DR:** With the default setup, News Intelligence uses **Widow (<WIDOW_HOST_IP>)** for the database, **not the NAS**. So normal app traffic does not go to the NAS and won’t compete with Plex on the NAS.

---

## Where does News Intelligence send traffic?

| Component        | Default target      | Hits NAS? |
|-----------------|---------------------|-----------|
| **Database**    | Widow <WIDOW_HOST_IP>:5432 | **No** (only if you use NAS rollback) |
| **Redis**       | localhost (or Docker)     | No |
| **API / Frontend** | localhost              | No |

So under default config, **no** News Intelligence traffic goes to the NAS. Plex and News Intelligence only share the same LAN; they don’t share the NAS.

---

## When *does* the NAS get used?

The NAS (<NAS_HOST_IP>) is only involved if you do one of the following:

1. **NAS database rollback**  
   You set `DB_HOST=localhost` and `DB_PORT=5433` and run the SSH tunnel to NAS. Then all DB traffic goes over the tunnel to the NAS. **Avoid this** if you want to keep NAS load low; stick with Widow.

2. **Log archive cron**  
   `scripts/setup_log_archive_cron.sh` can archive logs to a database. If that DB is on the NAS (tunnel), it will generate extra NAS traffic at 6:00 and 18:00. You can disable or reschedule that cron, or point it at Widow if you still want archiving.

3. **Backups to NAS storage**  
   Scripts like `db_backup.sh` / `db_backup_weekly.sh` use `BACKUP_BASE` (e.g. `/mnt/nas/backups`). If that path is on the NAS, backup runs will read from Widow and write to the NAS. You can:
   - Point backups to a local or Widow path instead, or  
   - Run backups at off‑peak times (e.g. early morning) so they don’t overlap with Plex.

4. **RSS / cron with NAS DB**  
   Some older cron examples use `DB_PORT=5433` (NAS tunnel). If you’re on Widow, your main RSS/collection should use the default (Widow). Check any custom crons and remove `DB_PORT=5433` so they use Widow.

---

## Recommendations to avoid NAS congestion

1. **Use Widow for the database**  
   Don’t use the NAS DB rollback unless you need it. Default:  
   `DB_HOST=<WIDOW_HOST_IP>` (or unset, so start_system.sh uses Widow).

2. **Don’t run the NAS SSH tunnel**  
   If you’re not doing NAS rollback, don’t start `setup_nas_ssh_tunnel.sh`. That way no News Intelligence process will talk to the NAS over SSH/PostgreSQL.

3. **Schedule heavy jobs off‑peak**  
   If you keep log archive or backups that touch the NAS, run them at times when you care less about Plex (e.g. 4:00 or 5:00).

4. **Optional: QoS on the router**  
   If Plex and other traffic still compete on the LAN, use router QoS to give Plex (or the NAS) higher priority. That’s independent of News Intelligence.

5. **Backups to local or Widow**  
   Set `BACKUP_BASE` to a path on your Pop machine or on Widow instead of `/mnt/nas/...` if you want zero backup traffic to the NAS.

---

## Quick check: is News Intelligence using the NAS?

- **start_system.sh**  
  If it prints “Using **Widow** database (direct) at <WIDOW_HOST_IP>:5432”, the app is **not** using the NAS for DB.

- **Tunnel**  
  If you don’t run `setup_nas_ssh_tunnel.sh` and don’t set `DB_HOST=localhost` / `DB_PORT=5433`, there is no NAS DB traffic.

- **Cron**  
  Run `crontab -l` and look for jobs that set `DB_PORT=5433` or that call scripts that write to NAS paths; adjust or disable those if you want to reduce NAS use.
