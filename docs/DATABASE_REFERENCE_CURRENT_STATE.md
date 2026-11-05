# DATABASE — Current State Reference

**Current as of:** 2026-11-04 (migration #254)  
**Status:** Complete — authoritative schema inventory for current deployment

---

## Schema Hierarchy

PostgreSQL `news_intel` database on Widow (`192.168.93.101:5432`) uses the following schema organization.

### Public schemas (shared infrastructure)

| Schema | Purpose | Key tables |
|--------|---------|------------|
| `public` | Domain catalog, ML queue, automation | `domains`, `domain_metadata`, `ml_processing_queue`, `automation_run_history`, `db_pool_pressure_advisory` |
| `intelligence` | Cross-domain intelligence products | See [Intelligence schemas](#intelligence-schemas-cross-domain) below |
| `pipeline` | Pipeline orchestration metadata | `pipeline_traces`, `pipeline_checkpoints`, `doc_index` |

### Domain silos (YAML-driven, per-topic)

Each domain silo is a PostgreSQL schema containing topic-specific tables. Silo provisioning uses YAML-driven definitions loaded via the contract module; inheritance defaults to **`politics`** (see [domain_silo_contract.py](../api/shared/domain_silo_contract.py) for `DEFAULT_CLONE_FROM_SCHEMA`).

### Intelligence schemas (cross-domain)

| Table | Purpose |
|-------|---------|
| `intelligence.contexts` | Article contexts / summaries |
| `intelligence.entity_profiles` | Canonical entity profiles |
| `intelligence.versioned_facts` | Historically versioned facts |
| `intelligence.content_refinement_queue` | Refinement pipeline queue |
| `intelligence.reference_events` | Longitudinal reference events |
| `intelligence.macro_series_observations` | Macro-series observations |
| `intelligence.sanctions_actions` | Sanctions action records |
| `intelligence.arc_definitions` | Arc definition metadata |
| `intelligence.arc_reports` | Generated arc reports |
| `intelligence.tracked_events` | Cross-domain event tracking |
| `intelligence.graph_connection_links` | Graph connection links |
| `intelligence.graph_connection_proposals` | Graph connection proposals |

### Current domain silo inventory (active)

Six domain silos are currently active. Each inherits from the base schema and adds extension tables as needed:

| Silo | Migration | Base tables | Extension tables | Notes |
|------|-----------|-------------|-----------------|-------|
| `politics` | #179/#183/#192 | articles, storylines, story_entity_index, rss_feeds | *(none)* | Default parent silo for cloning |
| `finance` | #179/#183/#192/#206 | articles, storylines, story_entity_index, rss_feeds | `market_patterns`, `corporate_announcements`, `financial_indicators`, `research_topics` | Consolidated from finance + finance_2 |
| `legal` | #177/#180 | articles, article_entities, storylines, entity_canonical, story_entity_index | *(none)* | Full entity extraction |
| `medicine` | #187/#192 | articles, article_entities, storylines, entity_canonical, story_entity_index, rss_feeds | *(none)* | Medical domain with RSS support |
| `artificial_intelligence` | #188/#192 | articles, article_entities, storylines, entity_canonical, story_entity_index, rss_feeds | *(none)* | AI domain with RSS support |
| `neurodiversity` | #254 | articles, article_entities, storylines, entity_canonical, story_entity_index | *(none)* | **Newest silo** — YAML-driven creation |

### Dropped / consolidated schemas (historical)

| Schema | Action | Migration | Reason |
|--------|--------|-----------|--------|
| `politics` → `politics_2` | Renamed | #197 (renamed), #219 (consolidated) | Consolidate politics domains |
| `finance` → `finance_2` | Renamed | #198 (renamed), #219 (consolidated) | Consolidate finance domains |
| `politics_2` | Dropped | #227 | FK constraints blocked full migration; consolidated into `politics` |
| `finance_2` | Dropped | #227 | FK anomalies in `intelligence.tracked_events`; finalized consolidation |
| `science_tech` | Dropped | #212 | Silo no longer needed — content moved to existing silos |

**FK anomaly detail:** Migrations #219 (consolidation) and #227 (drop) left residual FK references in `intelligence.tracked_events`. These are now handled via CASCADE or manual cleanup during consolidation. See migration files for details.

---

## Silo Inheritance Rules

### Default cloning target
Per `DEFAULT_CLONE_FROM_SCHEMA` in [domain_silo_contract.py](../api/shared/domain_silo_contract.py): **`politics`** is the default parent template for new domain silo creation.

### Clone semantics
When a new domain silo is created:
1. The base schema definition (tables + structure) is copied from `politics`
2. Domain-specific extension tables are added via YAML-driven provisioning
3. Migration entries are created in `db_version` for tracking

### Silo naming convention
- Domains use snake_case names matching the topic: `artificial_intelligence`, `neurodiversity`, etc.
- No numeric suffixes on active silos (historical ones had `_2` during consolidation phase)

---

## Core table structures (per silo)

Each domain silo schema contains at minimum these base tables:

### `articles` — Central fact table

| Column | Type | Notes |
|--------|------|-------|
| `article_id` | uuid | PK, default gen_random_uuid() |
| `headline` | text | |
| `url` | text | Unique |
| `domain_silo` | text | FK to public.domains (nullable) |
| `published_at` | timestamp | Indexed |
| `scraped_at` | timestamp | Default now() |
| `content_type` | text | rss, article, podcast, video |
| `body` | text | Full scraped content |
| `summary` | text | Article context (intelligence.contexts fallback) |
| `raw_content_url` | text | Source link |
| `topic_keywords` | text[] | |
| `source_name` | text | RSS source or extractor |
| `source_type` | text | rss_feed, article_extractor |
| `external_id` | text | External system ID |
| `sentiment_score` | float | ML output |
| `language` | text | Default 'en' |
| `status` | text | pending → enriched → processed |

### `storylines` — Narrative summaries

| Column | Type | Notes |
|--------|------|-------|
| `id` | bigserial | PK |
| `name` | text | Required |
| `description` | text | Required |
| `articles_to_stories_json` | jsonb | Article-to-storyline mapping |
| `status` | text | active, archived, draft |
| `created_at` / `updated_at` | timestamp | Auto-managed |

### `rss_feeds` — RSS source registry

| Column | Type | Notes |
|--------|------|-------|
| `id` | bigserial | PK |
| `title` | text | Required |
| `url` | text | Unique |
| `active` | boolean | Default true |
| `domain_silo` | text | FK to public.domains |
| `content_type` | text | rss, article, podcast, video |

### Entity tables (entity extraction silos)

| Table | Purpose |
|-------|---------|
| `article_entities` | Extracted entities per article |
| `story_entity_index` | Cross-reference: story ↔ entity |
| `entity_canonical` | Canonical entity names/aliases |

### Finance-specific extension tables

| Table | Purpose |
|-------|---------|
| `market_patterns` | Market trend patterns |
| `corporate_announcements` | Corporate news items |
| `financial_indicators` | Economic indicator data |
| `research_topics` | Finance research topic mappings |

---

## Known anomalies and caveats

1. **FK constraint gaps:** During the #197–#219 consolidation, residual FK references in `intelligence.tracked_events` were not fully cleaned up from dropped schemas. These are handled via CASCADE deletes or manual cleanup during silo operations.

2. **politics_2 / finance_2 drops:** Migrations #226 and #227 dropped these schemas to consolidate entities. The entity data was migrated into `politics` and `finance` respectively before the drop. Verify no orphaned FKs in `intelligence.tracked_events` after any future consolidation.

3. **science_tech removal:** Migration #212 removed the science_tech silo entirely. Any remaining articles were not reassigned (confirmed empty).

4. **Default entity extraction:** The `politics` silo is the default entity extraction template because `DEFAULT_CLONE_FROM_SCHEMA` points to it in domain_silo_contract.py.

---

## Migration summary timeline (key events)

| # | Date/Period | Schema change | Description |
|---|-------------|---------------|-------------|
| #177–#180 | Initial | `legal` created | Legal domain with entity extraction |
| #179/#183 | Initial | `politics`, `finance` created | Base silo schemas (articles, storylines, etc.) |
| #187 | Pre-consolidation | `medicine` created | Medical domain with RSS support |
| #188 | Pre-consolidation | `artificial_intelligence` created | AI domain with RSS support |
| #192 | Consolidation I | Base silos standardized | All silos aligned to common base structure |
| #197 | Consolidation II | politics → politics_2 | Renamed for consolidation phase |
| #198 | Consolidation II | finance → finance_2 | Renamed for consolidation phase |
| #206 | Post-consolidation | `finance` extensions | Finance-specific extension tables added |
| #212 | Cleanup | science_tech dropped | Silo no longer needed |
| #219 | Consolidation III | Entity migration into politics/finance | Final data merge from _2 schemas |
| #226/#227 | Consolidation III | politics_2, finance_2 dropped | Finalized consolidation; FK anomalies noted |
| #247–#251 | YAML-driven | Silo metadata management | New silo definition framework (#247) with CRUD routes and validation (#251) |
| #253 | Silo lifecycle | `science` dropped + re-created | Demonstrated silo drop/create cycle via API |
| #254 | Current | `neurodiversity` created | Newest domain — YAML-driven creation |

---

## Operational notes

- **Adding a new silo:** Use the [Silo Management API](../api/routes/silo_management.py) or YAML definition loader. The silo will be cloned from `politics` by default (`DEFAULT_CLONE_FROM_SCHEMA`).
- **Verifying silo inventory:** Query `public.domains` for registered domains; query `information_schema.schemata` for active PostgreSQL schemas.
- **Silo drop:** Use the Silo Management API's drop endpoint or manually DROP SCHEMA with CASCADE. Verify no orphaned FKs afterward, especially in `intelligence.tracked_events`.
- **Extension tables:** Finance is currently the only silo with extension tables (`market_patterns`, `corporate_announcements`, `financial_indicators`, `research_topics`). Future silos may need similar extensions defined via YAML or migration files.

---

*This document serves as the authoritative reference for the current database state. Update when new silos are created, dropped, or consolidated.*