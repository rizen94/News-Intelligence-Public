# Longitudinal intelligence — phase progress

**Last updated:** 2026-05-26  
**Owner:** operator + Cursor agents  
**MemPalace:** wing `News Intelligence`, room `pipeline_handoff`

---

## Phase 0 — Foundation hardening ✅

| Task | Status |
|------|--------|
| Backlog diagnosis + monitor alignment | done |
| Migration 221 provenance | applied Widow |
| Claim requeue (15,315) | done |
| Backup policy doc + cold archive script | done |
| Weekly backup cron | **installed** Widow (Sun 04:30 UTC) |
| Claim→fact chunked promotion (`CLAIMS_TO_FACTS_CHUNK_SIZE`) | done |
| 72h throughput in diagnose script | done |

---

## Phases 1–5 — Infrastructure through UI ✅

| Area | Status |
|------|--------|
| Migrations 221–227 | applied Widow |
| Seeds: 28 reference events, 2 arcs | loaded |
| Politics RSS (17 feeds) + environment (10 feeds) with `arc_relevance` | specs + YAML |
| pgvector + embeddings (articles, reference, Wikipedia) | done |
| Wikidata QID backfill + review queue API | done |
| Services + automation phases | done |
| API `/api/intelligence/*` | live |
| Web: Spine, Brief, Heatmap, Analogues, CitationDrawer | built |
| Golden eval harness (18 questions) | done |

---

## Phase 6 — Operator workflow ✅

| Task | Status |
|------|--------|
| `arc_report_feedback` + reference flags (migration 224) | applied |
| Reference event create / supersede / flag API | done |
| Arc report section feedback API + slow_report boost | done |
| Briefing filter arc feedback re-ranking | done |
| **Arc curation UI** (`/{domain}/arcs/curation`) | done |
| **Weekly Brief useful-section buttons** | done |
| Operator runbook | [`docs/LONGITUDINAL_OPERATOR_RUNBOOK.md`](../../LONGITUDINAL_OPERATOR_RUNBOOK.md) |

---

## Phase 2 external data — env-gated runtime

| Item | Notes |
|------|--------|
| ACLED ingest | set `ACLED_API_KEY`, `ACLED_EMAIL` |
| UCDP API | client ready |
| Sanctions OFAC + EU + UN | `SANCTIONS_INGEST_ENABLED=true` |
| GPR/EPU CSV | drop files in `api/config/imports/` |
| V-Dem / Freedom House CSV | `vdem_export.csv`, `freedom_house_export.csv` |
| EIA / Federal Register | `TRADE_RESOURCES_IMPORT_ENABLED=true`, optional `EIA_API_KEY` |
| Kiwix | `KIWIX_WIKIPEDIA_REST_URL` |

---

## Quick links

- Execution plan: [`docs/LONGITUDINAL_INTELLIGENCE_EXECUTION.md`](../../LONGITUDINAL_INTELLIGENCE_EXECUTION.md)
- Operator Sunday ritual: [`docs/LONGITUDINAL_OPERATOR_RUNBOOK.md`](../../LONGITUDINAL_OPERATOR_RUNBOOK.md)
- Widow setup: `./scripts/finish_longitudinal_widow_setup.sh`
