# Changelog

All notable changes to News Intelligence are documented here.

## [10.1.0] — Unreleased

### Added

- **Feature registry** (`api/config/features.yaml`) — lifecycle tags (`under_developed`, `staged`, `incorporated`, `deprecated`, `archived`), programmatic search CLI/API, rollover protocol
- **Signal-first admission control** — enabled by default; adaptive quality threshold governor
- **RSS feed silencing** — enabled with dry-run default; warn-then-auto-silence
- **Pipeline status table** — narrow eligibility store replacing hot JSONB scans (interim)
- **Spine work queues** — `content_enrichment_queue`, `unified_intake_queue`, `spine_tail_queue`
- **Claim resolvability gate** — seeded-pool check before claim insert; gap catalog for unresolvable subjects
- **Co-mention edge aggregation** — upsert increments with hard relationship cap
- **`drain_phase.py`** — unified operator CLI replacing catch-up script family
- **VERSION SSOT** — repo-root `VERSION` file; API and web surfaces unified at `10.1.0`

### Changed

- **Scheduling** — four loops: ingest maintenance, spine conductor (ordered), assembly conductor (ordered), nightly window
- **Intake fusion exclusive** — legacy per-article extract phases archived; unified intake sole LLM path
- **Steady-state model** — `qwen2.5:14b-instruct` for unified intake when quality gate passes
- **Monitor** — measures `profiles_updated`, `compiled`, `chronicle_entries` in batch throughput

### Removed

- Superseded intake schedulers: `entity_extraction`, `event_extraction`, `sentiment_analysis`, `quality_scoring`, `ml_processing`, `metadata_enrichment` (archived under `api/_archived/intake/`)
- POST_SPINE_RETIRED automation handlers extracted to `api/_archived/automation/retired_phase_handlers.py` (~1000 lines removed from `automation_manager.py`)
- Duplicate trees: `scripts/ni_review/`, `web/_archived_duplicates/`; ~40 root investigation markdowns moved to `docs/_archive/agent_investigations_2026/`
- NRI shim services moved to `api/_archived/services/`; `relationship_extraction` archived (entity_organizer uses `link_indexer_service`)
- Redundant catch-up entry points consolidated into `drain_phase.py` (archived scripts under `api/_archived/scripts/`)

### Migration

- 249–260: feature overrides, admission config, pipeline_status, spine queue tables (see `docs/UPGRADE_10.1.md`)
