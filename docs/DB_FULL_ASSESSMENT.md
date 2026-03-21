# Full database assessment — alignment, persistence, operations

**Purpose:** Living artifact for the **Full Database Assessment and Cleanup** plan: four-surface alignment (DB, API, web, processing), process-to-DB persistence, baseline snapshots, and cross-cutting expert checks.  
**Do not edit the plan file** in `.cursor/plans/`; update this doc as the system evolves.

---

## 1. Baseline snapshot (record per environment)

Re-run diagnostics when assessing a new environment; paste summary under a dated heading.

**Commands (from repo root):**

```bash
PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py
PYTHONPATH=api uv run python api/scripts/diagnose_db_legacy_data.py
uv run python scripts/check_v7_data_collection.py
PYTHONPATH=api uv run python scripts/db_full_inventory.py
PYTHONPATH=api uv run python scripts/db_persistence_gates.py
```

### 1.1 Dev / configured DB — 2026-03-20 (example capture)

| Check | Result |
|-------|--------|
| verify_migrations_160_167 | All OK (133, 160–172, **176** `applied_migrations`) |
| diagnose_db_legacy_data | `public.articles/storylines/rss_feeds` = 0 rows; ~122 unqualified `articles`/`storylines`/`rss_feeds` references in API code (see report output); no storyline_articles orphans in domain schemas |
| check_v7_data_collection | Article counts per domain; `content_enrichment` no success in 24h; document_processing / storyline_synthesis / daily_briefing active |
| db_full_inventory | Many **empty** tables in `public` are legacy templates—cross-check against four-surface matrix before any bundle C |
| bundle A (dev) | Migration **176** applied; `register_applied_migration.py 176`; `db_maintenance_analyze.py` (ANALYZE) on hot tables |

**Multi-environment:** Repeat with `DB_HOST` / `DB_NAME` / `.env` for **staging** and **production**; keep separate subsections (1.2 Staging, 1.3 Production).

---

## 2. Four-surface alignment matrix

Each row is one **feature slice**. Extend as features are added. **Deprecation:** mark `deprecated` only after pre-delete checklist in [DB_CLEANUP_BUNDLES.md](DB_CLEANUP_BUNDLES.md).

| Feature slice | Database | API (path pattern) | Web (route + client) | Processing (phase / service) |
|---------------|----------|--------------------|------------------------|------------------------------|
| Articles list/detail | `{domain}.articles` | `/api/{domain}/articles`, article by id | `/:domain/articles`, `ArticleDetail`; `web/src/services/api/articles.ts` | `collection_cycle` → RSS; `article_processing` / ML phases |
| RSS feeds | `{domain}.rss_feeds` | `/api/{domain}/rss_feeds` | `/:domain/rss_feeds` | `collection_cycle` |
| Storylines | `{domain}.storylines`, `storyline_articles` | `/api/{domain}/storylines` | `/:domain/storylines/*` | `storyline_*` phases, synthesis |
| Topics | `{domain}.topics`, `article_topic_assignments` | `/api/{domain}/topics` | `/:domain/topics` | `topic_clustering` |
| Contexts (Discover) | `intelligence.contexts`, `article_to_context` | context-centric routes under `/api/` | `/:domain/discover` | `context_sync` |
| Tracked events (Investigate) | `intelligence.tracked_events` | `/api/...` event routes | `/:domain/investigate`, `EventDetail` | `event_tracking`, `event_coherence_review` |
| Extracted timeline events | `public.chronological_events` | `/api/{domain}/events` (discrete events) | `/:domain/events` | `event_extraction`, `event_deduplication`, `timeline_generation` |
| Entities / dossiers | `{domain}.entity_canonical`, `article_entities`; `intelligence.entity_*` | entity + dossier routes | `/:domain/investigate/entities/*` | `entity_extraction`, `entity_dossier_compile`, … |
| Documents | `intelligence.processed_documents` | document routes | `/:domain/investigate/documents/*` | `document_processing`, `document_collection` |
| Monitoring | `public.automation_run_history`, `automation_state`, rollups | `/api/system_monitoring/*` | `/:domain/monitor` | All phases → `_persist_automation_run` |
| Watchlist | `{domain}.watchlist` | `/api/watchlist` (global) + domain variants | `/:domain/watchlist` | `watchlist_alerts` |
| Briefings / report | intelligence + domain synthesis fields | briefing/report API | `/:domain/briefings`, `/:domain/report` | `daily_briefing_synthesis`, synthesis services |

**Known gaps to track in backlog:** unqualified SQL on `articles` / `storylines` / `rss_feeds` in legacy services (see `diagnose_db_legacy_data.py` output) — must use domain schema or `search_path` set per connection.

---

## 3. Process-to-database persistence matrix

Automation phase names match `automation_manager.py` `task.name` values. **Proof column:** minimum durable signal that work happened (beyond `automation_run_history`).

| Phase | Primary writers (typical) | Proof of persistence |
|-------|---------------------------|----------------------|
| collection_cycle | `{domain}.articles`, `{domain}.rss_feeds` | New/updated articles; `last_fetched` on feeds |
| content_enrichment | `{domain}.articles` enrichment columns | `enrichment_status`, content length, `enrichment_attempts` |
| document_collection / document_processing | `intelligence.processed_documents` | New rows or updated extraction JSON |
| context_sync | `intelligence.contexts`, `article_to_context` | Context count / recent `created_at` |
| entity_extraction | `{domain}.article_entities`, `entity_canonical` | Rows linked to articles |
| event_extraction | `public.chronological_events` | New events (or explicit skip when none eligible) |
| event_deduplication | `chronological_events` columns | fingerprint/canonical updates |
| timeline_generation | storylines / events (service-dependent) | timeline artifacts per service code path |
| storyline_synthesis | `{domain}.storylines.synthesized_content` (or equivalent) | Updated storyline narrative fields |
| daily_briefing_synthesis | intelligence or domain briefing storage | Briefing rows or version bumps |
| entity_dossier_compile | `intelligence.entity_dossiers` | Updated dossier sections |
| automation (all) | `public.automation_run_history` | Always; upgrade failures to **warning** if insert fails |

**Verification:** run `scripts/db_persistence_gates.py` after a test window; extend gates as new proofs are defined.

---

## 4. Persistence verification gates

See [scripts/db_persistence_gates.py](../scripts/db_persistence_gates.py). Gates should fail (non-zero exit) when:

- DB unreachable
- Critical tables missing
- `automation_run_history` has no recent rows while API claims automation enabled (optional flag)

Extend with domain-specific row-count floors only when baselines are agreed (avoid flaky CI).

---

## 5. Expert cross-cutting checklist (DBA + full stack)

Use during assessment; record pass/fail in baseline section.

**Database:** connection pool vs workers; `statement_timeout`; transaction length; lock waits; FK vs orphan checks; index health; autovacuum/analyze; extension parity; `timestamptz` usage; roles/least privilege; backup restore drill.

**API/web:** response contracts vs TypeScript types; pagination limits; domain enforced server-side; error shape and correlation IDs.

**Processing:** idempotent retries; no long DB transactions around Ollama/RSS; config drift (`.env`, orchestrator YAML).

**Governance:** record applied migrations in `public.applied_migrations` (migration 176); ticket reference for any bundle C change.

---

## 6. Related docs

| Doc | Use |
|-----|-----|
| [PIPELINE_DB_ALIGNMENT_REPORT.md](PIPELINE_DB_ALIGNMENT_REPORT.md) | **Regenerate:** `PYTHONPATH=api uv run python scripts/verify_pipeline_db_alignment.py --write-report docs/PIPELINE_DB_ALIGNMENT_REPORT.md` — pipeline phases vs tables/columns + persistence signals |
| [DB_CLEANUP_BUNDLES.md](DB_CLEANUP_BUNDLES.md) | Bundle A/B/C templates, classification, pre-delete checklist |
| [DATABASE.md](DATABASE.md) | Schema overview |
| [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) | Frontend ↔ API wiring |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Operational issues |
| [DATA_CLEANUP_AND_COMPATIBILITY.md](DATA_CLEANUP_AND_COMPATIBILITY.md) | Legacy cleanup options (referenced by diagnose script) |

---

## 7. Production execution (runbook)

1. Maintenance window announced; on-call available.  
2. Fresh backup + verify artifact size (see `scripts/db_backup.sh`).  
3. Run baseline commands (§1); compare to last snapshot.  
4. Apply **bundle A** only from [DB_CLEANUP_BUNDLES.md](DB_CLEANUP_BUNDLES.md); re-run verify + persistence gates.  
5. **Bundle B** archive if any **bundle C** planned.  
6. **Bundle C** only per-object with pre-delete checklist + second person sign-off.  
7. Post: smoke tests (web critical paths), `db_persistence_gates.py`, `verify_migrations_160_167.py`.  
8. Optional: `scripts/db_maintenance_analyze.py` (or DBA-run `VACUUM ANALYZE` in window).

Staging should mirror steps 2–8 before production.
