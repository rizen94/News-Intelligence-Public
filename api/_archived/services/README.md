# Archived services

Unreferenced from routes, automation phases, scripts, and tests when archived. Kept for
rollback and forensics — do not import from `api/services/`.

## 2026-09 waste review

| File | Why |
|------|-----|
| `article_processing_service.py` | Legacy v3 per-article pipeline; superseded by the intake spine (`content_enrichment` → `unified_intake_extraction` → `spine_sql_tail`). Only reference was the `services` package re-export. |
| `content_validation_service.py` | Pre-spine content-availability gate; superseded by `shared/article_processing_gates.py`. |
| `maintenance_monitor.py` | v3.0 standalone resource monitor; superseded by `advanced_monitoring_service` + Monitor routes. |
| `quarantine_single_anchor_magnets.py` | Byte-identical copy of `api/scripts/quarantine_single_anchor_magnets.py`. |
| `quarantine_soft_magnet_episodes.py` | Stray fork of `api/scripts/quarantine_soft_magnet_episodes.py` that appends a third param to a two-placeholder SELECT — would raise if run. Operator copy in `api/scripts/` is the correct one. |
| `quiver_correlation.py` | Superseded by `congress_trade_signals_service` / `congress_trade_scoring_service`. `quiver_entity_resolver.py` stays in `api/services/` pending the in-flight Quiver work. |
| `run_major_backlog_catchup.py` | Dead fork of `api/scripts/run_major_backlog_catchup.py`; every `scripts/*.sh` invocation targets the `api/scripts/` path. Its one extra branch (`entity_profile_build`) is already covered by `get_all_pending_counts()`, which includes that key. |
| `shared_extraction_service.py` | Pre-unified extraction consolidator; superseded by `unified_intake_extraction_service`. |
| `topic_intelligence_service.py` | From `api/domains/content_analysis/services/`. No reference from any tracked source, YAML, or route; the only hits were a stale `diagnostics/discovery_report.*` and historical repomix dumps. Its module-scope singleton called `resolve_domain_schema()` in `__init__`, making it the last module in the tree that opened a DB connection at import — see `scripts/verify_no_import_time_db.py`. |
| `topic_clustering_service.py` (earlier) | Live implementation is `api/domains/content_analysis/services/topic_clustering_service.py`. |

## Sibling archives from the same review

- `api/_archived/utils/` — all of `api/utils/` (v3.0 `text_formatter`, `timeout_utils`, `module_reloader`); the directory had no `__init__.py` and no importers.
- `api/_archived/config/import_standards.py` + `api/_archived/scripts/fix_imports.py` — one-off import-normalisation tooling that only referenced each other.
- `api/_archived/modules/ml/iterative_rag_service.py` — v3.0 iterative RAG prototype; RAG now runs through `rag_evidence_pull_service` / `content_refinement_queue`.
