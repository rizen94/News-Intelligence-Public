# News Intelligence System — Database Reference

**Purpose:** Schema overview and data I/O — where data lives and who reads/writes it.  
**Version:** 8.0 | **Last updated:** March 2026

---

## 1. Overview

- **Assessment & alignment:** See [DB_FULL_ASSESSMENT.md](DB_FULL_ASSESSMENT.md) (four-surface matrix, persistence gates, baselines), [DB_CLEANUP_BUNDLES.md](DB_CLEANUP_BUNDLES.md), and [DB_PRODUCTION_MAINTENANCE_RUNBOOK.md](DB_PRODUCTION_MAINTENANCE_RUNBOOK.md).
- **Primary database:** PostgreSQL (default: Widow at `192.168.93.101:5432`, database `news_intel`, user `newsapp`).
- **Domain silos:** Per-domain schemas `politics`, `finance`, `science_tech` hold articles, storylines, topics, RSS feeds, and entity tables.
- **Shared intelligence:** Schema `intelligence` holds cross-domain entities, contexts, claims, events, dossiers, and related tables. Schema `orchestration` holds investigations and optional run history.
- **Finance auxiliary:** SQLite files in `data/finance/` (market data, evidence ledger, orchestrator state) and ChromaDB for vector search. See §4.

---

## 2. PostgreSQL schema layout

### 2.1 Public

| Table | Purpose |
|-------|---------|
| `domains` | Domain registry: `domain_key` (politics, finance, science-tech), `schema_name`, `is_active`, `display_order`, `config` (JSONB). |
| `domain_metadata` | Per-domain counts (article_count, topic_count, storyline_count, feed_count) and last_updated. |
| `applied_migrations` | Operational ledger of which migration IDs were applied in this environment (migration 176); populate via `api/scripts/register_applied_migration.py`. |

### 2.2 Per-domain schemas (`politics`, `finance`, `science_tech`)

Each active domain has a schema with the same logical structure (created by migrations 122, 125, 138, etc.):

| Table | Purpose |
|-------|---------|
| `articles` | Raw and processed articles: title, content, url, source, published_at, status, ml_data (JSONB), quality_score, summary, sentiment, feed_id, **`timeline_processed`** (event/timeline extraction gate; migration **177**), etc. |
| `rss_feeds` | Feed URL, name, is_active, last_fetched, fetch_interval, domain_key. |
| `storylines` | Story clusters: title, description, status, automation_enabled, editorial_document (JSONB), created_at, updated_at. |
| `storyline_articles` | Many-to-many: storyline_id, article_id. |
| `topic_clusters` | Topic name, domain, cluster metadata. |
| `article_topic_assignments` | Links articles to topics; relevance_score, context columns. |
| `article_keywords` | Thematic keywords per article (no dates/countries). |
| `entity_canonical` | Canonical entities: canonical_name, entity_type (person, organization, subject, recurring_event), aliases (TEXT[]), description, wikipedia_page_id. UNIQUE(canonical_name, entity_type). |
| `article_entities` | Per-article mentions: article_id, entity_name, entity_type, canonical_entity_id → entity_canonical.id, mention_source, confidence. |
| `article_extracted_dates` | Dates extracted from article text (excluded from topic clustering). |
| `article_extracted_times` | Times extracted from article text. |
| `watchlist` | Watchlist entries (domain-scoped). |
| Other | Feeds/storyline/topic indexes, automation settings, banned topics, etc. |

**Data I/O (per-domain):**

- **Written by:** RSS collector (articles, rss_feeds), article processing (ml_data, status, entities), entity extraction (article_entities, entity_canonical), topic clustering (topic_clusters, article_topic_assignments), storyline CRUD and automation (storylines, storyline_articles), watchlist.
- **Read by:** All domain-scoped API routes (articles, feeds, storylines, topics, entities), context processor (to build intelligence.contexts), synthesis and editorial pipelines.

### 2.3 Intelligence schema (`intelligence`)

Cross-domain and context-centric data. Entity IDs in intelligence tables refer to domain `entity_canonical.id` in the domain’s schema (no cross-schema FKs).

| Table | Purpose |
|-------|---------|
| `contexts` | Canonical content units: title, content, raw_content, domain_key, source_article_id, metadata. Bridge from domain articles to claims/events. |
| `article_to_context` | Maps article_id (per domain) to context_id. |
| `entity_profiles` | Living profiles per canonical entity: domain_key, entity_id (that domain’s entity_canonical.id), sections (JSONB), compiled content. |
| `old_entity_to_new` | Maps previous entity_canonical.id to entity_profiles.id for lineage after merges. |
| `extracted_claims` | Claims from contexts: context_id, claim_text, domain_key, entity_ids, confidence, etc. |
| `tracked_events` | Time-bounded events: title, description, domain_key, key_participant_entity_ids, event_chronicles (JSONB), editorial_briefing (JSONB), start_date, end_date. |
| `entity_dossiers` | Dossier per entity: entity_profile_id, domain_key, entity_id, summary, sections (JSONB). |
| `entity_positions` | Position/statements per entity (extracted or manual). |
| `processed_documents` | PDF/document metadata and extracted content (section/entity/findings); domain_key. |
| `pattern_discoveries` | Discovered patterns (domain_key, pattern_type, data JSONB). |
| `narrative_threads` | domain_key, storyline_id (in that domain’s storylines), summary, linked_article_ids. |
| `entity_relationships` | Cross-entity links: source/target domain + entity_id, relationship_type, confidence. |
| `cross_domain_links` | Links between domains (links JSONB array). |
| `wikipedia_knowledge` | Local Wikipedia cache for entity descriptions. |
| Other | Investigation notes, fact log, story state queue, retention/cleanup tables. |

**Data I/O (intelligence):**

- **Written by:** Context processor (contexts, article_to_context), entity profile sync (entity_profiles, old_entity_to_new), claim extraction (extracted_claims), event chronicle builder (tracked_events), dossier compiler (entity_dossiers), position tracker (entity_positions), document processing (processed_documents), pattern recognition (pattern_discoveries), narrative thread builder, entity resolution (entity_relationships), Wikipedia backfill (wikipedia_knowledge), intelligence cleanup controller.
- **Read by:** Context-centric API, synthesis service, verification service, editorial document service, RAG, briefings, entity and event UIs.

### 2.4 Orchestration schema (`orchestration`)

| Table | Purpose |
|-------|---------|
| `investigations` | Investigations (entity_ids refer to domain entity_canonical). |
| `events` | Append-only event log (e.g. for newsroom orchestrator). |
| `automation_run_history` | History of automation runs (optional). |

**Data I/O:** Written by orchestrator/automation; read by monitoring and investigation UIs.

---

## 3. Data flow (summary)

| Stage | Writes to | Reads from |
|-------|-----------|------------|
| RSS / docs | `{domain}.articles`, `{domain}.rss_feeds` | — |
| ML / entity extraction | `{domain}.articles.ml_data`, `{domain}.article_entities`, `{domain}.entity_canonical`, topic tables | `{domain}.articles` |
| Context sync | `intelligence.contexts`, `intelligence.article_to_context` | `{domain}.articles` |
| Entity profile sync | `intelligence.entity_profiles`, `intelligence.old_entity_to_new` | `{domain}.entity_canonical` |
| Claim / event extraction | `intelligence.extracted_claims`, `intelligence.tracked_events` | `intelligence.contexts` |
| Human audit (UI) | `intelligence.context_grouping_feedback` | `intelligence.contexts`; migration **174**; see [UI_PIPELINE_AUDIT_GUIDE.md](UI_PIPELINE_AUDIT_GUIDE.md) |
| Storyline / editorial | `{domain}.storylines.editorial_document`, `intelligence.tracked_events.editorial_briefing` | `intelligence.contexts`, claims, events, entity_profiles |
| Synthesis / verification | — | `intelligence.*`, `{domain}.storylines`, `{domain}.articles` |
| Data cleanup | Prunes/archives old data; entity decouple splits bad merges | `intelligence.*`, `{domain}.*` |

---

## 4. Other stores (Finance and ops)

| Store | Location | Purpose |
|-------|----------|---------|
| **market_data.db** | `data/finance/` | Market data cache (e.g. gold, commodities). Written by Finance Orchestrator; read by finance API. |
| **evidence_ledger.db** | `data/finance/` | Evidence and provenance for analysis tasks. |
| **ChromaDB** | `data/finance/chroma/` | Vector store for EDGAR/evidence search. |
| **orchestrator_state.db** | `data/orchestrator_state.db` | OrchestratorCoordinator and governors state. |
| **Redis** | Docker (port 6379) | Optional cache/sessions. |

---

## 5. Migrations and schema source

- **Migrations:** **Active** `api/database/migrations/*.sql` (tip-of-repo upgrades; currently **176+**). **Archived** `api/database/migrations/archive/historical/*.sql` (older numbered DDL; runners still resolve these). Ledger: `public.applied_migrations` (after 176) — record applies with `api/scripts/register_applied_migration.py`, compare with `api/scripts/migration_ledger_report.py`. Domain silos: 122, 125; entity/article_entities: 138; intelligence: 141–144; orchestration: 140; events: 133; documents: 160; tracked_events.storyline_id: 171; etc.
- **Unified schema (logical):** `schema/unified_schema.json` describes tables and columns for reference; actual DDL is in migrations.
- **Connection:** Single source of truth is `api/shared/database/connection.py` (`get_db_config`, `get_db_connection`). Config from `.env` / `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_PASSWORD` (e.g. from `.db_password_widow` on Widow).

---

## 6. Related docs

- [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) — DB host, Widow, rollback to NAS.
- [DATABASE_CONNECTION_AUDIT.md](DATABASE_CONNECTION_AUDIT.md) — Connection consistency.
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — End-to-end flow.
