# Widow — Disaster Recovery Runbook

**Version:** 1.0  
**Last updated:** 2026-11-01  
**Scope:** Full-host catastrophic failure (hardware, OS corruption, unbootable systemd)  
**Related:** [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) · [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md) · [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## When to Use This Runbook

Use this runbook **only** when:

- Widow cannot boot or systemd cannot start any services
- Postgres data directory is corrupted or missing
- You need to rebuild the host from scratch and restore NI service
- A component has failed in a way that automated recovery scripts cannot fix

If Widow is partially healthy (some services running), use [TROUBLESHOOTING.md](TROUBLESHOOTING.md) instead.

---

## Pre-Requisites (Have Ready Before Starting)

| Item | Where | Why |
|------|-------|-----|
| NAS credentials (`/mnt/nas`) | Local notes or pass manager | Backup source for Postgres dump |
| SSH access to Widow | From another host | Remote diagnostics before rebuild |
| NI repository clone (or git remote) | Any machine with the codebase | Deploy code after OS install |
| PopOS credentials (`192.168.93.99`) | Local notes | Caddy reverse-proxy and PopOS workers depend on Widow being up |

---

## Step 1 — Diagnose (Can Widow Still Be Reached?)

```bash
# From PopOS or another LAN host:
ping 192.168.93.101
ssh pete@192.168.93.101 "systemctl list-units --failed"
```

**If SSH responds:** The host is alive. Skip to [Step 4](#step-4-targeted-recovery) and attempt service-by-service recovery before considering a rebuild.

**If SSH does not respond:** The host may be down. Wait 5 minutes (auto-hibernation), then try again. If still unreachable after 10 minutes, proceed to rebuild.

---

## Step 2 — Verify Backups Exist on NAS

Before rebuilding, confirm backup data is reachable:

```bash
# Mount NAS and check for dumps
mount //192.168.93.100/NI_backups /mnt/nas/ni_backups -o username=pete,password=YOUR_NAS_PASS
ls -la /mnt/nas/ni_backups/

# Expected: daily dump (daily), weekly retention dumps (retained), log archives
```

**If NAS is unreachable or empty:** You will need to re-ingest all RSS data from scratch. Note the last known ingestion date for each domain so you can skip already-fetched feeds in `config.py`.

---

## Step 3 — Rebuild Widow (If Necessary)

### 3a. OS Install

1. Boot from Debian 12 live media
2. Install Debian 12 (minimal or server) to the USB root (`/dev/sda`)
3. Set hostname to `widow`
4. Create user `pete` with sudo privileges

### 3b. Base Packages

```bash
# From repository: scripts/deploy_to_widow.sh applies these, or run manually:
apt update
apt install -y python3 python3-venv nginx postgresql postgresql-client \
  ollama caddy git curl wget nfs-common

# Python deps
python3 -m venv /opt/news-intelligence/.venv
source /opt/news-intelligence/.venv/bin/activate
cd /opt/news-intelligence
pip install -r requirements.txt
```

### 3c. Deploy NI Code

```bash
# Copy from your dev machine or git clone:
rsync -avz --exclude '.git/' --exclude '__pycache__' \
  pete@popos:/path/to/News\ Intelligence/ \
  pete@192.168.93.101:/opt/news-intelligence/

# Or use the existing deploy script:
./scripts/deploy_to_widow.sh
```

---

## Step 4 — Targeted Recovery (When Widow Is Partially Healthy)

If SSH access works, try these in order before considering a full rebuild.

### 4a. Restart All Services

```bash
# On Widow:
sudo systemctl daemon-reload
sudo systemctl restart news-intelligence.target
/opt/news-intelligence/scripts/verify_widow_boot.sh
```

### 4b. Postgres-Only Recovery

If only Postgres is failing:

```bash
# Check if PG is running
sudo systemctl status postgresql

# If crashed — check logs
journalctl -u postgresql --since "1 hour ago" | tail -50

# Try starting fresh
sudo systemctl start postgresql
pg_isready -h localhost -p 5432 -U newsapp
```

### 4c. API-Only Recovery

If Postgres is up but the API won't respond:

```bash
# Check systemd unit
sudo systemctl status newsplatform-secondary
journalctl -u newsplatform-secondary --since "1 hour ago" --no-pager

# Kill stale process, restart
sudo pkill -f "uvicorn.*main:app"
sleep 2
sudo systemctl start newsplatform-secondary
curl -s --max-time 5 http://localhost:8000/api/system_monitoring/health
```

### 4d. Nginx / SSL Recovery

If public-facing service is down:

```bash
# Check nginx config
sudo nginx -t

# Reload config
sudo systemctl reload nginx

# Check cert expiry
openssl x509 -in /etc/letsencrypt/live/PUBLIC_DEMO_HOSTNAME/cert.pem -noout -enddate
```

---

## Step 5 — Full Restore from Backup

When you have a rebuilt Widow and confirmed backup on NAS:

### 5a. Restore Postgres

```bash
# Start PG fresh
sudo systemctl start postgresql

# Create user and database (if they don't exist)
sudo -u postgres psql <<'SQL'
CREATE USER newsapp WITH PASSWORD 'YOUR_PASSWORD';
CREATE DATABASE news_intel OWNER newsapp;
\q
SQL

# Restore from latest dump
gunzip -c /mnt/nas/ni_backups/latest_dump.sql.gz | psql -h localhost -U newsapp -d news_intel

# Verify restore
psql -h localhost -U newsapp -d news_intel -c "SELECT COUNT(*) FROM articles;"
psql -h localhost -U newsapp -d news_intel -c "SELECT COUNT(*) FROM stories;"
```

### 5b. Restore Configs

```bash
# .env from repo or backup
cp configs/.env.example /opt/news-intelligence/.env
# Fill in DB_PASSWORD from your notes

# Nginx config
cp nginx/widow-public-demo-site.conf.template /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/widow-public-demo-site.conf /etc/nginx/sites-enabled/
sudo systemctl reload nginx
```

### 5c. Verify Boot and Health

```bash
/opt/news-intelligence/scripts/verify_widow_boot.sh

# Manual verification:
curl -s --max-time 5 http://localhost:8000/api/system_monitoring/health
curl -s --max-time 3 http://localhost:3000 | head -1

# PopOS side — confirm Caddy proxies to Widow:
curl -I https://news-intelligence-ag.duckdns.org
```

### 5d. Verify Data Integrity

```bash
# Check domain article counts match pre-failure expectations
psql -h localhost -U newsapp -d news_intel <<'SQL'
SELECT schema_name, COUNT(*) FROM articles GROUP BY schema_name;
SELECT COUNT(*) FROM pipeline_state WHERE status = 'pending';
SELECT COUNT(*) FROM automation_queue WHERE status = 'pending';
SQL

# Run any missed batch jobs
python3 /opt/news-intelligence/scripts/widow-missed-nightly-recovery.py
```

---

## Step 6 — Post-Recovery Checklist

After restoring, verify these operational features are intact:

| Check | Command | Expected |
|-------|---------|----------|
| systemd target running | `systemctl status news-intelligence.target` | active (exited) or active (running) |
| API health | `curl localhost:8000/api/system_monitoring/health` | 200 OK with healthy payload |
| Frontend | `curl localhost:3000` | HTTP 200 |
| Nginx SSL | `nginx -t && systemctl status nginx` | config test passes, unit active |
| Postgres connectivity | `pg_isready -h localhost -p 5432 -U newsapp` | accepts connections |
| Health watchdog | `systemctl status widow-api-health-watchdog.timer` | timer active |
| Missed nightly recovery | `systemctl status widow-missed-nightly-recovery.timer` | timer active |
| DB probe (boot gate) | Check journal for `DB_PROBE_OK` on boot | present |
| cgroup memory limits | `cat /sys/fs/cgroup/system.slice/newsplatform-secondary.scope/memory.max` | set to non-empty value |

---

## Appendix A — Backup Inventory

| Backup Type | Script | Cron Schedule | Retention | Location |
|-------------|--------|---------------|-----------|----------|
| Latest daily dump | `scripts/db_backup_single_latest.sh` | Nightly (cron) | 1 file (latest) | Local `/opt/news-intelligence/backups/` |
| Weekly retained dumps | `scripts/db_backup_weekly_retained.sh` | Weekly (cron) | 4 weeks | NAS NFS share (`/mnt/nas/...`) |
| Log archive | log archival script | Periodic (cron) | Per cron schedule | NAS NFS share |

**Known gap:** There is currently **no automated alerting** for backup failures. If a backup job fails silently, no notification is sent. Manually verify the latest backup file's age and size periodically:

```bash
# Quick backup health check (run manually or add to monitoring):
find /opt/news-intelligence/backups/ -name "*.sql.gz" -mtime -2 -size +10k | wc -l
# Should return > 0. If 0, the latest daily backup failed.
```

---

## Appendix B — Known Failure Modes and Prevention

| Failure Mode | Prevention | Recovery Time Estimate |
|-------------|------------|----------------------|
| USB root wear-out (disk governor) | `widow_disk_io_governor.sh` + `journald-widow-usb-root.conf` already applied | Varies by drive condition |
| Postgres WAL corruption | Daily backup to NAS; `pg_rewind` if replica available later | 2-4 hours |
| Let's Encrypt cert expiry | **TODO:** Add certbot deploy hook (see Gap analysis) | Minutes once detected |
| cgroup memory OOM kill | `MemoryHigh=70%` + `MemoryMax=85%` already applied; watchdog restarts process | 2-4 minutes (watchdog cooldown) |
| NAS NFS mount drop | `missed-nightly-recovery` catches missing files; **TODO:** add NFS mount health check | Minutes to hours depending on mount recovery |

---

*This runbook should be reviewed and updated after any actual disaster recovery event.*
