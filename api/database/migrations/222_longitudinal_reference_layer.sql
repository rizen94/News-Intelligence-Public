-- Migration 222: Longitudinal intelligence reference layer + wikidata QID
-- Phase 1 — NI Longitudinal Intelligence. See docs/LONGITUDINAL_INTELLIGENCE_EXECUTION.md

BEGIN;

-- Wikidata QID on all domain entity_canonical tables
DO $$
DECLARE
  r RECORD;
  stmt TEXT;
BEGIN
  FOR r IN
    SELECT DISTINCT schema_name
    FROM public.domains
    WHERE schema_name IS NOT NULL AND schema_name <> ''
  LOOP
    stmt := format(
      $sql$
      ALTER TABLE %I.entity_canonical
          ADD COLUMN IF NOT EXISTS wikidata_qid text;
      CREATE INDEX IF NOT EXISTS idx_%I_entity_canonical_wikidata_qid
          ON %I.entity_canonical (wikidata_qid)
          WHERE wikidata_qid IS NOT NULL AND wikidata_qid <> '';
      $sql$,
      r.schema_name, r.schema_name, r.schema_name
    );
    EXECUTE stmt;
  END LOOP;
END $$;

-- Reference events (append-only curated history)
CREATE TABLE IF NOT EXISTS intelligence.reference_events (
    id bigserial PRIMARY KEY,
    event_date timestamptz NOT NULL,
    end_date timestamptz,
    date_precision text NOT NULL DEFAULT 'day'
        CHECK (date_precision IN ('day', 'month', 'year')),
    title text NOT NULL,
    summary text NOT NULL,
    category text,
    entity_qids text[] NOT NULL DEFAULT '{}',
    sources jsonb NOT NULL DEFAULT '[]'::jsonb,
    confidence text NOT NULL DEFAULT 'reference'
        CHECK (confidence IN ('reference', 'curated', 'verified')),
    curator text,
    arc_ids text[] NOT NULL DEFAULT '{}',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    superseded_by_id bigint REFERENCES intelligence.reference_events(id),
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW(),
    ingestion_date timestamptz NOT NULL DEFAULT NOW(),
    vintage_date timestamptz
);

CREATE INDEX IF NOT EXISTS idx_reference_events_event_date
    ON intelligence.reference_events (event_date DESC);
CREATE INDEX IF NOT EXISTS idx_reference_events_arc_ids
    ON intelligence.reference_events USING gin (arc_ids);
CREATE INDEX IF NOT EXISTS idx_reference_events_entity_qids
    ON intelligence.reference_events USING gin (entity_qids);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reference_events_slug
    ON intelligence.reference_events ((metadata->>'seed_id'))
    WHERE metadata->>'seed_id' IS NOT NULL AND metadata->>'seed_id' <> '';

CREATE TABLE IF NOT EXISTS intelligence.reference_event_corrections (
    id bigserial PRIMARY KEY,
    reference_event_id bigint NOT NULL REFERENCES intelligence.reference_events(id),
    correction_type text NOT NULL DEFAULT 'supersede'
        CHECK (correction_type IN ('supersede', 'date_fix', 'summary_fix', 'entity_fix')),
    prior_snapshot jsonb NOT NULL,
    new_reference_event_id bigint REFERENCES intelligence.reference_events(id),
    curator text,
    notes text,
    created_at timestamptz NOT NULL DEFAULT NOW()
);

-- Arc definitions (YAML sync + DB cache for queries)
CREATE TABLE IF NOT EXISTS intelligence.arc_definitions (
    arc_id text PRIMARY KEY,
    display_name text NOT NULL,
    description text,
    start_date date,
    end_date date,
    primary_entity_qids text[] NOT NULL DEFAULT '{}',
    primary_macro_series_ids text[] NOT NULL DEFAULT '{}',
    chapters jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    updated_at timestamptz NOT NULL DEFAULT NOW()
);

-- Generated arc reports (weekly briefs)
CREATE TABLE IF NOT EXISTS intelligence.arc_reports (
    id bigserial PRIMARY KEY,
    arc_id text NOT NULL REFERENCES intelligence.arc_definitions(arc_id),
    generated_at timestamptz NOT NULL DEFAULT NOW(),
    living_cutoff_date timestamptz NOT NULL,
    report_type text NOT NULL DEFAULT 'weekly_brief'
        CHECK (report_type IN ('weekly_brief', 'material_change', 'manual')),
    title text,
    content_markdown text NOT NULL DEFAULT '',
    sections jsonb NOT NULL DEFAULT '{}'::jsonb,
    citations jsonb NOT NULL DEFAULT '[]'::jsonb,
    validation jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_arc_reports_arc_generated
    ON intelligence.arc_reports (arc_id, generated_at DESC);

-- Macro series with vintage (FRED/ALFRED, GPR, EPU, V-Dem)
CREATE TABLE IF NOT EXISTS intelligence.macro_series_observations (
    id bigserial PRIMARY KEY,
    series_id text NOT NULL,
    observation_date date NOT NULL,
    value numeric,
    vintage_date timestamptz NOT NULL DEFAULT NOW(),
    source text NOT NULL DEFAULT 'fred',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    UNIQUE (series_id, observation_date, vintage_date, source)
);

CREATE INDEX IF NOT EXISTS idx_macro_series_obs_series_date
    ON intelligence.macro_series_observations (series_id, observation_date DESC);

-- External events (ACLED, UCDP normalized)
CREATE TABLE IF NOT EXISTS intelligence.external_events (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    external_id text NOT NULL,
    event_date timestamptz NOT NULL,
    end_date timestamptz,
    title text NOT NULL,
    summary text,
    country_code text,
    region text,
    event_type text,
    fatalities integer,
    entity_qids text[] NOT NULL DEFAULT '{}',
    raw jsonb NOT NULL DEFAULT '{}'::jsonb,
    ingestion_date timestamptz NOT NULL DEFAULT NOW(),
    vintage_date timestamptz,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_external_events_event_date
    ON intelligence.external_events (event_date DESC);
CREATE INDEX IF NOT EXISTS idx_external_events_source
    ON intelligence.external_events (source);

-- Sanctions actions (OFAC, EU, UN)
CREATE TABLE IF NOT EXISTS intelligence.sanctions_actions (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    external_id text NOT NULL,
    action_date timestamptz NOT NULL,
    action_type text,
    entity_qids text[] NOT NULL DEFAULT '{}',
    entity_names text[] NOT NULL DEFAULT '{}',
    program text,
    summary text,
    raw jsonb NOT NULL DEFAULT '{}'::jsonb,
    ingestion_date timestamptz NOT NULL DEFAULT NOW(),
    vintage_date timestamptz,
    created_at timestamptz NOT NULL DEFAULT NOW(),
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_sanctions_actions_action_date
    ON intelligence.sanctions_actions (action_date DESC);

-- Citation registry for drawer lookups (maps citation_id → provenance)
CREATE TABLE IF NOT EXISTS intelligence.citation_registry (
    citation_id text PRIMARY KEY,
    source_type text NOT NULL,
    source_table text,
    source_row_id bigint,
    source_url text,
    quote text,
    confidence numeric,
    event_date timestamptz,
    ingestion_date timestamptz,
    vintage_date timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT NOW()
);

-- Materialized view stubs for Phase 5 UI aggregates (refresh via automation)
CREATE MATERIALIZED VIEW IF NOT EXISTS intelligence.mv_arc_spine_events AS
SELECT
    re.id AS reference_event_id,
    re.event_date,
    re.title,
    re.category,
    re.entity_qids,
    unnest(re.arc_ids) AS arc_id
FROM intelligence.reference_events re
WHERE re.superseded_by_id IS NULL
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_arc_spine_events_pk
    ON intelligence.mv_arc_spine_events (reference_event_id, arc_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS intelligence.mv_tension_heatmap_monthly AS
SELECT
    date_trunc('month', ee.event_date AT TIME ZONE 'UTC')::date AS month_start,
    COALESCE(ee.country_code, 'XX') AS region_key,
    ee.source,
    COUNT(*)::integer AS event_count,
    COALESCE(SUM(ee.fatalities), 0)::integer AS fatalities_sum
FROM intelligence.external_events ee
GROUP BY 1, 2, 3
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_tension_heatmap_monthly_pk
    ON intelligence.mv_tension_heatmap_monthly (month_start, region_key, source);

COMMIT;
