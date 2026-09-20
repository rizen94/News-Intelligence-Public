# NI + NRI Unification Cutover Runbook

> **Historical / superseded for day-to-day ops** — cutover completed June 2026. Current state: [PROJECT_STATUS.md](../PROJECT_STATUS.md), [INVESTIGATION.md](INVESTIGATION.md). `/api/nri/*` shims **removed**; use `/api/investigation/*` only.
>
> Single maintenance-window deploy to Widow (`192.168.93.101`).  
> Prep all code on branch `unification/big-bang` before scheduling downtime.

## Preconditions

- [ ] All plan todos complete on feature branch
- [ ] `scripts/verify_single_source_of_truth.py` passes (or only allowlisted exceptions)
- [ ] `cd api && PYTHONPATH=. python -c "from nri_core.services.integration import get_investigation_health"`
- [ ] Web build succeeds with `investigationApi` routes
- [ ] `pg_dump` disk space available on Widow

## 1. Stop parallel runtimes

```bash
# On Widow as root/sudo
sudo systemctl stop nri-api.service 2>/dev/null || true
sudo systemctl stop nri-mention-resolver.timer nri-mention-resolver.service 2>/dev/null || true
sudo systemctl stop nri-loop.timer nri-loop.service 2>/dev/null || true
sudo systemctl disable nri-api.service
sudo systemctl disable nri-mention-resolver.timer
sudo systemctl disable nri-loop.timer
```

Disable permanently (optional, after bake):

```bash
sudo systemctl mask nri-api.service nri-mention-resolver.timer nri-loop.timer
```

## 2. Stop NI API (brief downtime starts)

```bash
sudo systemctl stop news-intelligence-api-public
```

## 3. Database backup

```bash
sudo -u postgres pg_dump -Fc news_intel > /var/backups/news_intel_pre_unification_$(date +%Y%m%d).dump
# identity_spine if schema changed:
sudo -u postgres pg_dump -Fc identity_spine > /var/backups/identity_spine_pre_unification_$(date +%Y%m%d).dump
```

## 4. Apply schema migration

```bash
cd /opt/news-intelligence
psql -U newsapp -d news_intel -f api/database/migrations/237_investigation_schema_merge.sql
```

Verify:

```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'intelligence' AND tablename LIKE 'investigation_%' LIMIT 5;
```

## 5. Deploy code

```bash
cd /home/pete/Documents/projects/News\ Intelligence   # or rsync to /opt/news-intelligence
git checkout unification/big-bang
git pull   # or rsync from dev workspace
sudo rsync -a --delete api/ /opt/news-intelligence/api/
sudo rsync -a --delete web/dist/ /var/www/news-intelligence/   # after npm run build
```

## 6. Merge environment

Add to `/opt/news-intelligence/.env` (or production env):

```env
USE_INVESTIGATION_PREFIXED_TABLES=true
INVESTIGATION_SCHEMA=intelligence
INVESTIGATION_TABLE_PREFIX=investigation_
# Retire standalone NRI API proxy:
# NRI_API_URL=   (unset or remove)
```

Ensure `AUTOMATION_DISABLED_SCHEDULES` includes `context_sync` on Widow prod (cron authoritative).

## 7. Python venv / dependencies

```bash
cd /opt/news-intelligence/api
source .venv/bin/activate
pip install -r requirements.txt   # merged nri_core deps
PYTHONPATH=. python -c "from nri_core.services.integration import get_investigation_health; print('ok')"
```

## 8. Start services

```bash
sudo systemctl start news-intelligence-api-public
sudo systemctl start newsplatform-secondary
```

## 9. Verify

```bash
cd /opt/news-intelligence
API_BASE_URL=http://127.0.0.1:8000 scripts/verify_unification_cutover.sh
```

Expected:

- `/api/investigation/health` → `status: ok`
- `/api/nri/health` → same (legacy shim)
- `/api/investigation/resolution_stats` → metrics JSON
- `mention_resolution` phase runs in automation status (no nri-mention-resolver.timer)
- SSOT script passes

## 10. Rollback (if needed)

```bash
sudo systemctl stop news-intelligence-api-public
sudo -u postgres pg_restore -c -d news_intel /var/backups/news_intel_pre_unification_YYYYMMDD.dump
git checkout main   # or previous release tag
# redeploy + restart
sudo systemctl enable --now nri-api.service nri-mention-resolver.timer  # if reverting fully
```

## Post-cutover bake (1–2 weeks)

1. Monitor `mention_resolution` drain stats in API logs
2. Confirm no traffic to `:8010`
3. Drop `nri` schema compatibility views per migration tail SQL
4. Remove `/api/nri/*` shims when clients migrated

## Related docs

- [UNIFICATION_BASELINE.md](UNIFICATION_BASELINE.md) — pre-cutover inventory
- [INVESTIGATION.md](INVESTIGATION.md) — product/API reference
- [NRI_LOOP_OPERATOR_GUIDE.md](NRI_LOOP_OPERATOR_GUIDE.md) — unified operator manual for both loops
- [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md) — systemd units
