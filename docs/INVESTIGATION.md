# Investigation Product (formerly NRI)

> Internal package: `api/nri_core/` · Public API: `/api/investigation/*` · UI label: **Investigation**

## Overview

Investigation resolves entity mentions in news contexts to FollowTheMoney (FtM) identity spine records, parks ambiguous matches for human review, and exposes hypotheses, loop runs, and bridge QA for the Investigate UI.

NI and NRI are unified in-process after cutover — no standalone `:8010` API.

## API routes

| Route | Purpose |
|-------|---------|
| `GET /api/investigation/health` | Service health |
| `GET /api/investigation/resolved_mentions` | CEM → FtM resolution log |
| `GET /api/investigation/parked` | Ambiguous mentions awaiting review |
| `PATCH /api/investigation/parked/{id}` | Review parked mention |
| `GET /api/investigation/entity_bridge/{profile_id}` | NI profile ↔ FtM bridge |
| `GET /api/investigation/bridge_qa/audit` | Suspect/mismatch bridge audit |
| `GET /api/investigation/entity_claims` | Claims for bridged entity |
| `GET /api/investigation/context_intel/{context_id}` | Mentions + claims for context |
| `GET /api/investigation/hypotheses` | Shadow loop hypotheses |
| `GET /api/investigation/spine/entities` | Spine entity browser |
| `POST /api/investigation/spine/match` | Ad-hoc spine match |
| `GET /api/investigation/resolution_stats` | Resolver metrics |
| `GET /api/investigation/loop_runs` | Shadow loop history |
| `GET /api/investigation/ftm_cache_stats` | FtM cache by dataset |
| `GET /api/investigation/research_seeds` | Suggested research targets (velocity, claims, cross-domain) |
| `POST /api/investigation/research_seeds` | Seed research focus (FTM IDs, domains) |
| `GET /api/investigation/loop_summary` | Aggregated loop run summary |
| `GET /api/investigation/vault_index` | Consolidated vault inventory |

Legacy shim **removed** (June 2026 cutover bake). Use `/api/investigation/*` only.

TypeScript client: `web/src/services/api/investigationApi.ts`  
Route constants: `web/src/config/apiRoutes.ts`

## Schema

Pre-migration: `nri.*` tables in `news_intel`  
Post-migration: `intelligence.investigation_*` (set `USE_INVESTIGATION_PREFIXED_TABLES=true`)

Qualified names via `api/config/investigation_tables.py` — never hardcode `nri.` in new code.

`identity_spine` database is separate — spine ingest/resolution uses `database_targets.spine_dsn()`.

## Automation

`mention_resolution` phase in AutomationManager drains the CEM resolver (replaces `nri-mention-resolver.timer`).

Executor: `api/services/automation/executor.py`  
Runner: `api/nri_core/resolver_runner.py`

## Package layout

```
api/nri_core/
  services/integration.py   # API handlers + DB reads
  services/bridge_qa.py       # Bridge quality assessment
  services/entity_claims.py   # Entity claim queries
  evidence/mention_resolver.py
  spine/                      # Identity spine ingest + resolution
  loop/                       # Shadow hypothesis loop
```

Shim services (delegate to nri_core): `nri_integration_service.py`, `nri_bridge_qa_service.py`, `nri_entity_claims_service.py`

## UI pages

| Path | Page |
|------|------|
| `/:domain/investigate/entity-resolution` | Resolved + parked mentions |
| `/:domain/investigate/spine-browser` | FtM spine search |
| `/:domain/investigate/hypotheses` | Shadow hypotheses |
| `/:domain/operations/investigation-ops` | Ops dashboard + bridge QA |

Component: `web/src/components/nri/FtmBridgePanel.tsx` (FtM bridge card on entity pages)

## Operator references

- Cutover: [UNIFICATION_CUTOVER.md](UNIFICATION_CUTOVER.md)
- Baseline: [UNIFICATION_BASELINE.md](UNIFICATION_BASELINE.md)
- System audit: [NI_NRI_SYSTEM_AUDIT_2026-06.md](NI_NRI_SYSTEM_AUDIT_2026-06.md)
- **Operator Guide**: [NRI_LOOP_OPERATOR_GUIDE.md](NRI_LOOP_OPERATOR_GUIDE.md) — unified manual for both loops, vault outputs, research direction, and troubleshooting
