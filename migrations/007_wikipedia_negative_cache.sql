BEGIN;

CREATE TABLE IF NOT EXISTS intelligence.wikipedia_negative_cache (
    title_lower         TEXT PRIMARY KEY,
    entity_type         TEXT,
    reason              TEXT NOT NULL,
    methods_tried       TEXT[] NOT NULL DEFAULT '{}',
    attempts            INTEGER NOT NULL DEFAULT 1,
    sample_source_id    BIGINT,
    first_seen          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempted      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE intelligence.wikipedia_negative_cache IS
    'Entities that have been tried and confirmed unresolvable to Wikipedia.';

COMMENT ON COLUMN intelligence.wikipedia_negative_cache.reason IS
    'Why this entity was blocklisted: no_results, too_ambiguous, generic_term, ner_artifact, too_short, manual_block';

CREATE INDEX IF NOT EXISTS idx_neg_cache_reason
    ON intelligence.wikipedia_negative_cache (reason);
CREATE INDEX IF NOT EXISTS idx_neg_cache_last_attempted
    ON intelligence.wikipedia_negative_cache (last_attempted);

COMMIT;
