# v12 post-cutover ops (24–48h)

Run on Widow after `/opt` is on `12.0.0`. Do not start LAST (hops/SPA/LLM stakes) until this window looks healthy.

## Smoke

```bash
systemctl is-active news-intelligence-api-public.service
curl -s http://127.0.0.1:8000/ | jq -r .data.version   # expect 12.0.0

cd /opt/news-intelligence && set -a && . ./.env && set +a
PYTHONPATH=api .venv/bin/python - <<'PY'
from shared.episode_attach_gate import episode_container_assembly_enabled
from shared.assembly_link_funnel import automation_auto_attach_enabled
from shared.link_scoring import auto_republish_enabled
print("episode", episode_container_assembly_enabled())
print("absorb", automation_auto_attach_enabled())
print("auto_republish", auto_republish_enabled())
PY
```

## Collectors

| Source | Status | Next |
|--------|--------|------|
| Federal Register | Live (50 CE on cutover day) | Keep scheduled/manual runs |
| EDGAR | Live (56 CE); needs `EDGAR_USER_AGENT` | Keep |
| CourtListener | **Blocked** — `COURTLISTENER_API_TOKEN` missing on Widow `.env` | Add key name to Infisical / `.env`, then dry-run → live |

```bash
# After token is present (never paste into chat):
PYTHONPATH=api python api/scripts/run_public_data_collectors.py \
  --source courtlistener --dry-run --json
PYTHONPATH=api python api/scripts/run_public_data_collectors.py \
  --source courtlistener --json
```

Secret key name: **`COURTLISTENER_API_TOKEN`** (CourtListener “Token …” auth).

## Watch

- `closed_thin` package count (should rise as max-rounds escape fires — not stay at ready_for_editor)
- FR/EDGAR CE growth without upsert errors
- Episode attach logs: gate rejects vs bag absorb (absorb must stay off)
- **Bag write freeze (membership SSOT):** with `STORYLINE_ARTICLES_DUAL_WRITE=0`, `storyline_articles` must not grow

```bash
# Invariant: zero bag inserts in the last hour (run on Widow after membership_store deploy)
sudo -u postgres psql -d news_intel -c "
SELECT COUNT(*) AS bag_inserts_last_hour
FROM politics.storyline_articles
WHERE created_at > NOW() - INTERVAL '1 hour';
"
# Expect 0 when dual-write off and migration 298 trigger applied
```

Optional probe (mode + recent insert fingerprint):

```bash
cd /opt/news-intelligence && PYTHONPATH=api .venv/bin/python api/scripts/debug_sa_bag_write_probe.py
```

## Rollback archive

`/home/pete/backups/news-intelligence/opt-ni-v11-pre-12.0-2026-08-16.tgz`  
Tag file: `/opt/news-intelligence/.v12_cutover_archive_tag`

## LAST (hold)

See `v12_deferred_last_bucket.md`.
