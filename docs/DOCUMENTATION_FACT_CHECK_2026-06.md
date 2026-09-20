# Documentation Fact-Check — June 2026

**Ground truth source:** Widow (`192.168.93.101`) snapshot [`docs/generated/WIDOW_GROUND_TRUTH_2026-06-22.md`](generated/WIDOW_GROUND_TRUTH_2026-06-22.md)  
**Reproduce:** `cd /opt/news-intelligence && set -a && . .env && set +a && PYTHONPATH=api .venv/bin/python3 scripts/verify_documentation_ground_truth.py --write-report`

---

## Executive summary

| Area | Widow as-is | Doc drift (before this pass) | Status |
|------|-------------|------------------------------|--------|
| Pipeline domains | All 5 active + pipeline-active | AGENTS/PROJECT_STATUS said politics/finance only | **Fixed** (P0) |
| science-tech | No `science_tech` namespace | Listed as built-in / inactive | **Fixed** — retired (migration 212) |
| DB port | Apps `6432` (PgBouncer); admin `5432` | Docs said `:5432` only | **Fixed** (P0/P1) |
| Topic clustering | `topic_clusters` SSOT; `topic_keywords` all 5 schemas | PIPELINE_AND_AUTOMATION said `topics` | **Fixed** |
| NRI shims | `/api/investigation/*` only; `nri-api` disabled | INVESTIGATION listed `/api/nri/*` | **Fixed** |
| Cron filename | `/etc/cron.d/widow-db-adjacent` | PIPELINE_OPERATIONS said `news-intelligence-widow-db` | **Fixed** |
| Ollama dual routing | `OLLAMA_DUAL_HOST_ROUTING_ENABLED=true` | AGENTS said off by default | **Fixed** |
| Migration ledger | 241–245 registered 2026-06-22 | Ledger stopped at 233 | **Fixed** (Widow ops) |
| Storyline automation routes | Hardcoded politics/finance/science-tech regex | Blocked legal/medicine/AI | **Fixed** (code) |

---

## P0 — SSOT documents

### AGENTS.md §Domain Structure

| | |
|---|---|
| **Claim (stale)** | Built-in domains `politics`, `finance`, `science-tech`; pipeline = politics/finance only |
| **Widow evidence** | `public.domains`: legal, medicine, artificial-intelligence, politics, finance — all `is_active=true`; `get_pipeline_active_domain_keys()` returns all five |
| **Verdict** | Contradictory |
| **Remediation** | Doc edit — **done** |

### AGENTS.md §Database / Ollama

| | |
|---|---|
| **Claim (stale)** | Single port `:5432`; dual Ollama routing off unless deliberate |
| **Widow evidence** | `DB_PORT=6432`; `OLLAMA_DUAL_HOST_ROUTING_ENABLED=true`, `OLLAMA_POP_OS_HOST=192.168.93.99` |
| **Verdict** | Stale |
| **Remediation** | Doc edit — **done** |

### PROJECT_STATUS.md

| | |
|---|---|
| **Claim (stale)** | Database at `:5432` only; no five-domain table |
| **Widow evidence** | PgBouncer 6432 in prod `.env`; five registry domains pipeline-active |
| **Verdict** | Stale |
| **Remediation** | Doc edit — **done** |

---

## P1 — Operations documents

### PIPELINE_OPERATIONS_WIDOW.md

| | |
|---|---|
| **Claim (stale)** | Cron file `news-intelligence-widow-db` |
| **Widow evidence** | `/etc/cron.d/widow-db-adjacent` |
| **Verdict** | Stale |
| **Remediation** | Doc edit — **done** |

### PIPELINE_AND_AUTOMATION.md

| | |
|---|---|
| **Claim (stale)** | `topic_clustering` writes `topics` |
| **Widow evidence** | `topic_clusters`, `article_topic_clusters`, `topic_keywords` on all five schemas |
| **Verdict** | Stale |
| **Remediation** | Doc edit — **done** |

### WIDOW_DB_ADJACENT_CRON.md §4

| | |
|---|---|
| **Claim (stale)** | "Do not run a full FastAPI stack on Widow" |
| **Widow evidence** | `news-intelligence-api-public` active+enabled; AutomationManager in-process |
| **Verdict** | Contradictory |
| **Remediation** | Doc edit — **done** |

### DATABASE.md / SECRETS_AND_SETTINGS_INDEX.md

| | |
|---|---|
| **Claim (stale)** | Port `5432` for all clients |
| **Widow evidence** | `DB_PORT=6432` in application `.env` |
| **Verdict** | Stale |
| **Remediation** | Doc edit — **done** |

### INVESTIGATION.md / UNIFICATION_CUTOVER.md

| | |
|---|---|
| **Claim (stale)** | Active `/api/nri/*` shim |
| **Widow evidence** | `nri-api` disabled; cutover bake removed shims |
| **Verdict** | Stale |
| **Remediation** | Doc edit + historical banner on cutover doc — **done** |

### PIPELINE_ORCHESTRATION_HARMONY.md

| | |
|---|---|
| **Claim (stale)** | `nri-mention-resolver.timer` on Widow |
| **Widow evidence** | `mention_resolution` automation phase; timer disabled |
| **Verdict** | Stale |
| **Remediation** | Doc edit — **done** |

### DB_PRODUCTION_MAINTENANCE_RUNBOOK.md

| | |
|---|---|
| **Claim (missing)** | `run_migration.py` may apply without ledger row |
| **Widow evidence** | Migrations 241–245 applied but unregistered until 2026-06-22 |
| **Verdict** | Missing |
| **Remediation** | Doc edit — **done** |

---

## P2 — Reference docs (remaining drift)

These files still mention `science-tech` or politics/finance-only examples. **Not edited in this pass** — track for follow-up PR:

| File | Issue |
|------|-------|
| `docs/SYSTEM_OVERVIEW.md` | science-tech in domain diagram; default redirect `/politics` |
| `docs/API_REFERENCE.md` | Domain list politics/finance/science-tech |
| `docs/TROUBLESHOOTING.md` | science-tech in storyline discovery note |
| `docs/EVENTS_ZERO_AND_HOW_TO_POPULATE.md` | science-tech example |
| `docs/WIDOW_SERVER_MIGRATION_2026_06.md` | Historical; may conflict on Ollama/NAS — add banner when editing |

`docs/CODEBASE_MAP.md` — **fixed** (schema list + pipeline doc link).

---

## Code alignment (Phase 4)

| File | Change | Status |
|------|--------|--------|
| `storyline_automation.py`, `storyline_automation_bulk.py` | `DOMAIN_PATH_PATTERN` instead of hardcoded regex | **Deployed Widow** |
| `scripts/verify_pipeline_db_alignment.py` | Registry-driven `DOMAIN_SCHEMAS`; topic cluster checks | **Deployed Widow** |
| `api/scripts/diagnose_pipeline_pathways.py` | `get_pipeline_active_domain_keys()` loops | **Deployed Widow** |
| `api/scripts/backfill_editorial_ledes.py` | Already registry-driven via `public.domains` | No change needed |
| `web/src/utils/domainHelper.ts` | Five-domain `FALLBACK_DOMAINS`; no `politics_2` fallback | **In dev tree** |

---

## Widow verification (Phase 5)

| Check | Result |
|-------|--------|
| `verify_documentation_ground_truth.py --write-report` | **exit 0** |
| `verify_pipeline_db_alignment.py` | **exit 0** (all 5 silos) |
| Migrations 241–245 in `applied_migrations` | **Registered** 2026-06-22 |
| `GET /api/system_monitoring/registry_domains` | 200 |
| `GET /api/legal/storylines/review-queue/count` | **200** (was blocked by regex) |
| `news-intelligence-api-public` restart | **done** |

---

## Automation scripts added

| Script | Purpose |
|--------|---------|
| `scripts/verify_documentation_ground_truth.py` | Reproducible Widow/host snapshot (domains, env, systemd, cron, ledger, topic tables) |

Extended: `scripts/verify_pipeline_db_alignment.py` — pipeline-active schema fan-out + topic cluster table checks.

---

*Last verified: 2026-06-22 on Widow.*
