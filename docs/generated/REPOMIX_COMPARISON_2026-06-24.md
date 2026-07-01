# Repomix comparison — 2026-06-24 vs June baseline

Generated from `unification/big-bang` dev workspace. Baselines frozen as `repomix-output-2026-06-15.baseline.md` and `repomix-nri-output-2026-06-16.baseline.md`.

## Summary

| Pack | Baseline | Current (2026-06-24) | Δ files | Δ bytes | Repomix tokens |
|------|----------|----------------------|---------|---------|----------------|
| **NI** (`repomix-widow.config.json`) | 1,050 files / 3.33 MB | 1,215 files / 3.59 MB | **+165 net** (+177 / −12) | +255 KB | **910,057** (was ~841k per Jun audit) |
| **NRI** (`repomix-nri.config.json`) | 81 files / 62 KB | 87 files / 65 KB | **+6** | +2.7 KB | **17,713** (was ~22k in Jun audit — smaller include scope) |

Regenerate:

```bash
repomix -c repomix-widow.config.json -o repomix-output-2026-06-24.md
repomix -c repomix-nri.config.json -o repomix-nri-output-2026-06-24.md
python3 scripts/compare_repomix_snapshots.py --old repomix-output-2026-06-15.baseline.md --new repomix-output-2026-06-24.md --label NI
```

**Note:** Prod `/opt/news-intelligence` was not redeployed; this pack reflects the dev tree, not live Widow prod.

---

## Refactor checklist (present in new NI pack)

| Area | Path | In new pack? |
|------|------|--------------|
| Entity routes | `api/domains/intelligence_hub/routes/entity_resolution.py` | yes |
| Entity facade | `api/services/entity_service_facade.py` | yes |
| API deprecation | `api/shared/api_deprecation.py` | yes (2 references) |
| Shared kernel | `api/shared/kernel/domain_events.py` | yes |
| Article query facade | `api/shared/services/article_query_service.py` | yes |
| Scheduler manifest | `api/config/schedulers.yaml` | yes |
| Runtime kernel | `api/config/runtime.py` | yes |
| Config index | `api/config/CONFIG_INDEX.md` | **no** — not in repomix include globs (`docs/**/*.md` only); exists in repo |
| Service catalog | `docs/BACKGROUND_SERVICES.md` | yes |
| Entity contracts | `docs/ENTITY_SERVICES.md` | yes |
| NRI vault validator | `api/nri_core/vault/validator/firewall.py` | yes (NI + NRI packs) |

Symbol grep: `deprecated_gone_response` 0 → 2; `entity_service_facade` 0 → 8 references in NI pack.

---

## Improvements by refactor phase

### Phase 1 — API consolidation

- **Entity routes extracted** — `entity_resolution.py` added; resolution HTTP handlers decoupled from `context_centric.py`.
- **Unified deduplication** — `api/domains/content_analysis/routes/deduplication.py` added; removed `article_deduplication.py` and `rss_duplicate_management.py`.
- **Storyline route modularization** — `storyline.py`, `automation.py` added; legacy `storyline_automation*.py` routes removed.
- **Health consolidation** — `api/domains/system_monitoring/routes/health.py`, `domain_health_check.py` added.
- **HTTP 410 legacy endpoints** — `api_deprecation.py` + `deprecated_gone_response` in news aggregation routes.
- **Investigation routes** — `api/domains/intelligence_hub/routes/investigation.py` in-process.

### Phase 2 — Domain boundaries

- **Shared kernel** — `api/shared/kernel/domain_events.py`, `article_query_service.py` (finance/evidence paths use facade instead of direct `ArticleService` imports).
- **Full `api/nri_core/`** — 76+ new files in NI pack (evidence, loop, spine, services, vault).

### Phase 3 — Configuration

- **`api/config/runtime.py`** — Ollama/DB SSOT, `validate_runtime_config()`.
- **`api/config/schedulers.yaml`** — consolidation rotation + automation manifest.
- **`api/config/database_targets.py`**, **`investigation_tables.py`** — investigation unification.
- Migrations **237–246** — investigation schema merge, `nri` drop, topic index, science-tech purge.

### Phase 4 — Background services

- **`docs/BACKGROUND_SERVICES.md`** — worker catalog.
- **`api/shared/services/worker_health.py`**, **`service_result.py`** — heartbeat + envelope helpers.
- Consolidation scheduler reads YAML manifest (in modified `consolidation_scheduler.py`).

### Phase 5 — Service layer

- **`entity_service_facade.py`** — single entry for entity ops from routes.
- **`api/shared/text_similarity.py`** — shared string similarity.
- **`docs/ENTITY_SERVICES.md`** — facade contracts.

### NRI pack delta (+6 files)

- `api/nri_core/evidence/bridge_qa.py`
- `api/nri_core/vault/` — `validator/firewall.py`, `reader/hypothesis_reader.py`
- Import normalization: `nri_core.loop.*` / `nri_core.llm.*` (replacing legacy `loop.*` / `llm.*`)

---

## Notable removals / archives

| Removed from pack | Reason |
|-------------------|--------|
| `api/collectors/enhanced_rss_collector.py` | Archived → `api/_archived/collectors/` |
| `web/src/pages/Finance/*.tsx` (5 pages) | Moved to `web/_archived_duplicates/` |
| `web/src/pages/Operations/NriOpsPage.tsx` | Replaced by `InvestigationOpsPage.tsx` |
| Duplicate storyline/automation/dedup route files | Consolidated into unified routers |

---

## Validation cross-check

- Unit tests: **185** NI + **12** `nri_core` passing (dev workspace, `.env`).
- Widow restart (2026-06-24): `verify_widow_boot.sh` PASSED; readiness `ready: true`.
- SSOT lint: `scripts/verify_single_source_of_truth.py` passed on critical paths.

---

## Config notes

- Added ignore patterns to `repomix-widow.config.json`: `news-intelligence-kit/**`, `.cursor/**` (permission-denied dirs).
- Repomix security check excluded 2 files from NI pack (sensitive patterns in `docs/CODING_STYLE_GUIDE.md` and one other).
- Structural stats: `repomix-stats-2026-06-24.json` (metadata-only, token tree).

---

## Artifacts

| File | Role |
|------|------|
| `repomix-output-2026-06-15.baseline.md` | Frozen NI baseline |
| `repomix-output-2026-06-24.md` | Current NI pack |
| `repomix-nri-output-2026-06-16.baseline.md` | Frozen NRI baseline |
| `repomix-nri-output-2026-06-24.md` | Current NRI pack |
| `repomix-stats-2026-06-24.json` | NI token tree (no file bodies) |
| `scripts/compare_repomix_snapshots.py` | Repeatable diff tool |
