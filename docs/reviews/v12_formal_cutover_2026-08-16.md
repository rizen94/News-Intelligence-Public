# v12 formal cutover — 2026-08-16

**Status:** complete (MUST + THIN on Widow `/opt`)  
**Lab:** PopOS `News Intelligence` `release/12.0` → `12.0.0`  
**Prod:** Widow `/opt/news-intelligence`

## Actions

1. Lab preflight: pytest `test_v12_must_thin.py` **12 passed**; episode on; absorb/dual-write/auto-republish off; pipeline `ordered`.
2. Rollback archive retained: `~/backups/news-intelligence/opt-ni-v11-pre-12.0-2026-08-16.tgz` (tag file `.v12_formal_cutover_archive_tag`). A second full tar was aborted (oversized I/O); use the v11 archive for rollback.
3. Stopped `news-intelligence-api-public.service`; rsynced lab → `/opt` (exclude `.venv` / `.env` / data / logs).
4. Applied + ledgered migration **297** (`closed_thin`) on prod (`applied_migrations` notes: `v12 closed_thin formal cutover`).
5. Started API; smoke green.

## Smoke results

| Check | Result |
|-------|--------|
| API version | `12.0.0` |
| nginx health | HTTP 200 |
| `episode_container_assembly` | true |
| bag absorb | false |
| SA dual-write | false → `write_allowed` false |
| auto-republish | false |
| room loop | false |
| `storyline_automation` retired | true |
| act-verb kernel + stakes gate files | present |
| SA derived-membership write gate | present |
| `closed_thin` packages | **3** (`intelligence`) |
| CourtListener token | **missing** — collector stays skipped |
| `EDGAR_USER_AGENT` | **missing** on Widow env at smoke — EDGAR may skip until set |

## Follow-ups (not blockers for MUST/THIN code cutover)

- Infisical / Widow `.env`: `COURTLISTENER_API_TOKEN`, confirm `EDGAR_USER_AGENT`
- 24–48h ops: `docs/reviews/v12_post_cutover_ops.md`
- LAST bucket held: hops / Edition SPA / LLM stakes

## Rollback

```bash
sudo systemctl stop news-intelligence-api-public.service
# restore from ~/backups/news-intelligence/opt-ni-v11-pre-12.0-2026-08-16.tgz into /opt
sudo systemctl start news-intelligence-api-public.service
```
