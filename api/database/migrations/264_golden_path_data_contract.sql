-- Golden path data contract (documentation in DB + deprecated table comments)
-- See docs/GOLDEN_PATH_DATABASE.md
--
-- ID 264: ledger already has 263 = graph_pattern_refusal_and_link_status (2026-07-11).
-- Do not reuse 263. This file creates infrastructure.data_path_contract.

BEGIN;

CREATE SCHEMA IF NOT EXISTS infrastructure;

CREATE TABLE IF NOT EXISTS infrastructure.data_path_contract (
    stage TEXT PRIMARY KEY,
    read_objects TEXT NOT NULL,
    write_objects TEXT NOT NULL,
    notes TEXT
);

INSERT INTO infrastructure.data_path_contract (stage, read_objects, write_objects, notes)
VALUES
    (
        'rss_intake',
        '{schema}.rss_feeds',
        '{schema}.articles',
        'schema = politics, finance, etc. from public.domains'
    ),
    (
        'body_enrichment',
        '{schema}.articles',
        '{schema}.articles (content, enrichment_status)',
        'article_content_enrichment_service; summary is separate'
    ),
    (
        'reader_dek',
        '{schema}.articles.summary, {schema}.storylines.editorial_document',
        '{schema}.articles.summary OR editorial fields',
        'home_feed.py; content alone is not dek today'
    ),
    (
        'storyline_canonical',
        '{schema}.storylines, {schema}.storyline_articles',
        'same',
        'Reader primary path'
    ),
    (
        'storyline_suggestions_queue',
        'public.storyline_article_suggestions',
        'public.storyline_article_suggestions',
        'Must promote to domain silo; FKs to public.storylines removed in mig 232'
    ),
    (
        'automation_run_history',
        'infrastructure.automation_run_history',
        'infrastructure.automation_run_history',
        'Migrated from public in migration 230'
    )
ON CONFLICT (stage) DO UPDATE SET
    read_objects = EXCLUDED.read_objects,
    write_objects = EXCLUDED.write_objects,
    notes = EXCLUDED.notes;

COMMENT ON TABLE public.articles IS
    'LEGACY STUB — DO NOT USE. Domain articles live in {schema}.articles (politics, finance, …).';

COMMENT ON TABLE public.storylines IS
    'LEGACY STUB — DO NOT USE. Domain storylines live in {schema}.storylines.';

COMMENT ON TABLE public.storyline_articles IS
    'LEGACY STUB — DO NOT USE. Domain links live in {schema}.storyline_articles.';

COMMENT ON TABLE public.storyline_article_suggestions IS
    'Staging queue for storyline membership (domain_key required). Promote to {schema}.storyline_articles; not a reader source of truth.';

COMMIT;
