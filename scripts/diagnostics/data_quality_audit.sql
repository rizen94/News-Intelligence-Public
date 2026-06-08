-- News Intelligence — read-only data quality audit (packs 0–5)
-- Run via: psql, Postgres MCP execute_sql, or scripts/diagnostics/run_data_quality_audit.py
-- Database: news_intel (Widow). Do not run writes in this file.

-- =============================================================================
-- PACK 0 — Environment and catalog
-- =============================================================================

-- @section pack_0_1_database
-- Interpretation: confirms target DB and total size.
SELECT current_database() AS db_name,
       pg_size_pretty(pg_database_size(current_database())) AS db_size;

-- @section pack_0_2_domains
-- Interpretation: active silos drive all per-domain loops (use is_active = true).
SELECT domain_key, schema_name, is_active, display_order
FROM public.domains
ORDER BY display_order, domain_key;

-- @section pack_0_3_schema_table_counts
-- Interpretation: table count per schema; unexpected schemas may be legacy residue.
SELECT table_schema, count(*) AS table_count
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
  AND table_type = 'BASE TABLE'
GROUP BY table_schema
ORDER BY table_count DESC;

-- @section pack_0_4_largest_relations
-- Interpretation: storage hotspots; large JSONB/text tables are dedupe candidates.
SELECT n.nspname AS schema_name,
       c.relname AS relation_name,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
       pg_total_relation_size(c.oid) AS total_bytes
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'm')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 30;

-- =============================================================================
-- PACK 1 — Data inventory and freshness
-- =============================================================================

-- @section pack_1a_global_intelligence
-- Interpretation: row counts and date span for global intelligence tables.
SELECT 'contexts' AS relation_name,
       count(*)::bigint AS row_count,
       min(created_at) AS min_ts,
       max(created_at) AS max_ts
FROM intelligence.contexts
UNION ALL
SELECT 'article_to_context', count(*), min(created_at), max(created_at)
FROM intelligence.article_to_context
UNION ALL
SELECT 'extracted_claims', count(*), min(created_at), max(created_at)
FROM intelligence.extracted_claims
UNION ALL
SELECT 'tracked_events', count(*), min(created_at), max(created_at)
FROM intelligence.tracked_events
UNION ALL
SELECT 'entity_profiles', count(*), min(created_at), max(created_at)
FROM intelligence.entity_profiles
UNION ALL
SELECT 'processed_documents', count(*), min(created_at), max(created_at)
FROM intelligence.processed_documents
UNION ALL
SELECT 'versioned_facts', count(*), min(created_at), max(created_at)
FROM intelligence.versioned_facts
UNION ALL
SELECT 'content_refinement_queue', count(*), min(created_at), max(created_at)
FROM intelligence.content_refinement_queue
UNION ALL
SELECT 'article_duplicate_sources', count(*), min(first_seen_at), max(last_seen_at)
FROM intelligence.article_duplicate_sources
UNION ALL
SELECT 'automation_run_history', count(*), min(started_at), max(started_at)
FROM public.automation_run_history
ORDER BY relation_name;

-- @section pack_1a_contexts_by_domain
-- Interpretation: context volume per domain_key.
SELECT domain_key, count(*) AS contexts,
       max(created_at) AS latest_context
FROM intelligence.contexts
GROUP BY domain_key
ORDER BY contexts DESC;

-- @section pack_1a_tracked_events_narratives
-- Interpretation: share of tracked events with generated narrative spine/lenses.
SELECT count(*) AS events_total,
       count(*) FILTER (WHERE global_narrative IS NOT NULL AND btrim(global_narrative) <> '') AS has_global_narrative,
       count(*) FILTER (WHERE narrative_lenses IS NOT NULL AND narrative_lenses::text NOT IN ('null', '{}', '[]')) AS has_lenses
FROM intelligence.tracked_events;

-- @section pack_1a_refinement_queue_status
-- Interpretation: backlog vs completed refinement jobs.
SELECT status, count(*) AS jobs, min(created_at) AS oldest, max(created_at) AS newest
FROM intelligence.content_refinement_queue
GROUP BY status
ORDER BY jobs DESC;

-- @section pack_1c_coverage_funnel_template
-- Replace :schema with active schema_name (e.g. politics). Repeat per domain.
-- Interpretation: pipeline-stage coverage for one silo.
/*
SELECT
  count(*) AS articles_total,
  count(*) FILTER (WHERE url IS NOT NULL AND btrim(url) <> '') AS has_url,
  count(*) FILTER (WHERE content IS NOT NULL AND length(btrim(content)) > 100) AS has_body_100,
  count(*) FILTER (WHERE enrichment_status = 'enriched') AS enriched,
  count(*) FILTER (WHERE summary IS NOT NULL AND length(btrim(summary)) > 50) AS has_summary,
  count(*) FILTER (WHERE quality_score IS NOT NULL) AS has_quality_score,
  count(*) FILTER (WHERE ml_data IS NOT NULL) AS has_ml_data,
  count(*) FILTER (WHERE entities IS NOT NULL AND entities::text NOT IN ('[]', 'null')) AS has_entities_json
FROM politics.articles
WHERE enrichment_status IS DISTINCT FROM 'removed';
*/

-- =============================================================================
-- PACK 2 — Duplicates and redundant storage
-- =============================================================================

-- @section pack_2b_multi_context_per_article
-- Interpretation: articles linked to more than one context (bridge redundancy).
SELECT domain_key, article_id, count(*) AS context_links
FROM intelligence.article_to_context
GROUP BY domain_key, article_id
HAVING count(*) > 1
ORDER BY context_links DESC
LIMIT 50;

-- @section pack_2b_orphan_contexts
-- Interpretation: contexts with no article_to_context row.
SELECT count(*) AS orphan_contexts
FROM intelligence.contexts c
WHERE NOT EXISTS (
  SELECT 1 FROM intelligence.article_to_context m WHERE m.context_id = c.id
);

-- @section pack_2b_orphan_context_classification
-- Interpretation: orphan buckets — pdf_section is often by design; legacy domain_key from migrations 210/211.
SELECT
  c.source_type,
  c.domain_key,
  count(*) AS orphan_count
FROM intelligence.contexts c
WHERE NOT EXISTS (
  SELECT 1 FROM intelligence.article_to_context m WHERE m.context_id = c.id
)
GROUP BY c.source_type, c.domain_key
ORDER BY orphan_count DESC;

-- @section pack_2b_orphan_legacy_domain_keys
-- Interpretation: orphans on retired silo keys (investigate bridge cleanup, not new contexts).
SELECT domain_key, count(*) AS orphan_count
FROM intelligence.contexts c
WHERE NOT EXISTS (
  SELECT 1 FROM intelligence.article_to_context m WHERE m.context_id = c.id
)
  AND domain_key IN ('politics', 'finance', 'science-tech')
GROUP BY domain_key
ORDER BY orphan_count DESC;

-- @section pack_2c_claim_duplicates
-- Interpretation: duplicate claim triples per context (dedupe phase target).
SELECT context_id,
       lower(btrim(subject_text)) AS subject_n,
       lower(btrim(predicate_text)) AS predicate_n,
       lower(btrim(object_text)) AS object_n,
       count(*) AS dup_count
FROM intelligence.extracted_claims
WHERE subject_text IS NOT NULL AND object_text IS NOT NULL
GROUP BY 1, 2, 3, 4
HAVING count(*) > 1
ORDER BY dup_count DESC
LIMIT 50;

-- @section pack_2c_entity_profile_duplicates
-- Interpretation: multiple profiles for same canonical in a domain.
SELECT domain_key, canonical_entity_id, count(*) AS profile_rows
FROM intelligence.entity_profiles
WHERE canonical_entity_id IS NOT NULL
GROUP BY domain_key, canonical_entity_id
HAVING count(*) > 1
ORDER BY profile_rows DESC
LIMIT 50;

-- @section pack_2c_claims_missing_fields
-- Interpretation: low-quality extracted claims.
SELECT count(*) FILTER (WHERE subject_text IS NULL OR btrim(subject_text) = '') AS missing_subject,
       count(*) FILTER (WHERE object_text IS NULL OR btrim(object_text) = '') AS missing_object,
       count(*) AS total
FROM intelligence.extracted_claims;

-- @section pack_2e_processed_documents_failures
-- Interpretation: dead weight in document pipeline.
SELECT count(*) AS docs_total,
       count(*) FILTER (WHERE metadata->'processing'->>'permanent_failure' = 'true') AS permanent_failures,
       count(*) FILTER (WHERE extracted_sections IS NULL OR extracted_sections = '[]'::jsonb) AS no_sections
FROM intelligence.processed_documents;

-- =============================================================================
-- PACK 3 — Pipeline efficiency
-- =============================================================================

-- @section pack_3a_automation_phase_stats
-- Interpretation: run volume, success rate, duration by phase (7d window).
SELECT phase,
       count(*) FILTER (WHERE started_at > now() - interval '24 hours') AS runs_24h,
       count(*) FILTER (WHERE started_at > now() - interval '7 days') AS runs_7d,
       round(100.0 * avg(CASE WHEN success THEN 1.0 ELSE 0.0 END)
             FILTER (WHERE started_at > now() - interval '24 hours'))::numeric, 1) AS success_pct_24h,
       round(avg(extract(epoch FROM (completed_at - started_at)))
             FILTER (WHERE started_at > now() - interval '24 hours' AND completed_at IS NOT NULL))::numeric, 1)
           AS avg_duration_s_24h
FROM public.automation_run_history
WHERE started_at > now() - interval '7 days'
GROUP BY phase
ORDER BY runs_24h DESC NULLS LAST, runs_7d DESC;

-- @section pack_3a_automation_recent_failures
-- Interpretation: phases failing in last 24h.
SELECT phase, count(*) AS failures_24h
FROM public.automation_run_history
WHERE started_at > now() - interval '24 hours'
  AND NOT success
GROUP BY phase
ORDER BY failures_24h DESC
LIMIT 20;

-- =============================================================================
-- PACK 4 — Output quality
-- =============================================================================

-- @section pack_4a_quality_score_distribution_template
-- Per schema; replace politics.
/*
SELECT width_bucket(quality_score::float, 0, 1, 10) AS bucket,
       count(*) AS articles
FROM politics.articles
WHERE quality_score IS NOT NULL
GROUP BY 1
ORDER BY 1;
*/

-- @section pack_4b_storylines_missing_summary_template
/*
SELECT count(*) AS storylines_total,
       count(*) FILTER (WHERE analysis_summary IS NULL OR length(btrim(analysis_summary)) < 200) AS short_or_missing_summary,
       count(*) FILTER (WHERE master_summary IS NULL OR length(btrim(master_summary)) < 200) AS short_or_missing_master
FROM politics.storylines;
*/

-- =============================================================================
-- PACK 5 — Structural / schema drift
-- =============================================================================

-- @section pack_5_applied_migrations
-- Interpretation: recent migration ledger entries.
SELECT migration_id, applied_at, environment, left(notes, 80) AS notes_preview
FROM public.applied_migrations
ORDER BY applied_at DESC NULLS LAST
LIMIT 25;

-- @section pack_5_core_tables_per_active_domain
-- Interpretation: missing expected tables per active silo.
WITH expected AS (
  SELECT unnest(ARRAY[
    'articles', 'storylines', 'storyline_articles', 'rss_feeds', 'article_entities'
  ]) AS table_name
),
domains AS (
  SELECT domain_key, schema_name FROM public.domains WHERE is_active = true
)
SELECT d.domain_key,
       d.schema_name,
       e.table_name,
       EXISTS (
         SELECT 1
         FROM information_schema.tables t
         WHERE t.table_schema = d.schema_name
           AND t.table_name = e.table_name
       ) AS table_exists
FROM domains d
CROSS JOIN expected e
ORDER BY d.domain_key, e.table_name;

-- @section pack_5d_legal_storylines_health
-- Interpretation: post-fsck integrity spot-check for legal silo.
SELECT count(*) AS legal_storylines FROM legal.storylines;

-- =============================================================================
-- AUDIT DASHBOARD — single-row KPI summary (compare to Monitor backlog)
-- =============================================================================

-- @section audit_dashboard
-- Interpretation: global headline KPIs; per-domain totals from run_data_quality_audit.py.
SELECT
  (SELECT count(*)::bigint FROM intelligence.contexts) AS contexts_total,
  (SELECT count(DISTINCT (domain_key, article_id))::bigint FROM intelligence.article_to_context)
    AS articles_with_context_link,
  (SELECT count(*)::bigint FROM intelligence.extracted_claims) AS extracted_claims_total,
  (SELECT count(*)::bigint FROM (
     SELECT 1 FROM intelligence.extracted_claims
     WHERE subject_text IS NOT NULL AND object_text IS NOT NULL
     GROUP BY context_id,
              lower(btrim(subject_text)),
              lower(btrim(predicate_text)),
              lower(btrim(object_text))
     HAVING count(*) > 1
   ) g) AS claim_duplicate_groups,
  (SELECT round(100.0 * avg(CASE WHEN success THEN 1.0 ELSE 0.0 END), 1)
   FROM public.automation_run_history
   WHERE started_at > now() - interval '24 hours') AS automation_success_pct_24h,
  (SELECT max(started_at) FROM public.automation_run_history) AS latest_automation_run;
