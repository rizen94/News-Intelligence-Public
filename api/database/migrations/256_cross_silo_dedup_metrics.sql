-- Migration 256: Persistent cross-silo deduplication metrics tables
-- Replaces expensive live UNION-ALL cross-silo GROUP-BY queries in /system_monitoring/status.
-- The dedup pipeline writes per-silo aggregates after each run; the monitoring endpoint
-- reads a single indexed lookup on intelligence.dedup_metrics instead of scanning every domain.

CREATE SCHEMA IF NOT EXISTS intelligence;

-- ── 1. Per-silo daily aggregate cache ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS intelligence.dedup_metrics (
    id            BIGSERIAL PRIMARY KEY,
    silo          VARCHAR(100)    NOT NULL,       -- domain schema_name (politics, finance, …)
    metric_date   DATE            NOT NULL DEFAULT CURRENT_DATE,
    articles_seen BIGINT          NOT NULL DEFAULT 0,
    url_duplicates      BIGINT NOT NULL DEFAULT 0,
    content_hash_duplicates BIGINT NOT NULL DEFAULT 0,
    articles_with_hash  BIGINT NOT NULL DEFAULT 0,
    last_run_at   TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    UNIQUE (silo, metric_date)
);

COMMENT ON TABLE intelligence.dedup_metrics IS 'Per-silo daily deduplication aggregates written by the pipeline.';

CREATE INDEX IF NOT EXISTS idx_dedup_metrics_date ON intelligence.dedup_metrics(metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_dedup_metrics_silo_date ON intelligence.dedup_metrics(silo, metric_date DESC);

-- ── 2. Cross-silo tracking table (every article instance involved in a dedup event) ─
CREATE TABLE IF NOT EXISTS intelligence.dedup_cross_silo (
    id              BIGSERIAL PRIMARY KEY,
    content_hash    VARCHAR(64),                       -- SHA-256 of article body; NULL for URL-only matches
    dup_group_id    UUID            DEFAULT gen_random_uuid(),  -- groups articles that are duplicates
    instance_url    TEXT,
    source_silo     VARCHAR(100)        NOT NULL,
    primary_silo    VARCHAR(100),                    -- where the surviving row lives
    detected_at     TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    action_taken    VARCHAR(32)   DEFAULT 'identified'  -- identified / merged / manual_review
);

COMMENT ON TABLE intelligence.dedup_cross_silo IS 'Individual article instances involved in cross-silo deduplication.';

CREATE INDEX IF NOT EXISTS idx_dedup_cs_hash    ON intelligence.dedup_cross_silo(content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dedup_cs_group   ON intelligence.dedup_cross_silo(dup_group_id);
CREATE INDEX IF NOT EXISTS idx_dedup_cs_detected ON intelligence.dedup_cross_silo(detected_at DESC);

-- ── 3. Convenience view: latest per-silo snapshot ────────────────────────────
DROP VIEW IF EXISTS intelligence.v_dedup_metrics_latest;
CREATE OR REPLACE VIEW intelligence.v_dedup_metrics_latest AS
SELECT dm.*
FROM intelligence.dedup_metrics dm
WHERE dm.metric_date = (
    SELECT MAX(dm2.metric_date)
    FROM intelligence.dedup_metrics dm2
    WHERE dm2.silo = dm.silo
);

-- ── 4. Helper: aggregate across all silos into a single summary row for today ─
DROP FUNCTION IF EXISTS intelligence.rebuild_daily_dedup_metrics(DATE);
CREATE OR REPLACE FUNCTION intelligence.rebuild_daily_dedup_metrics(p_date DATE DEFAULT CURRENT_DATE)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    rec         RECORD;
    v_silo      TEXT;
    v_url_dup   BIGINT := 0;
    v_ch_dup    BIGINT := 0;
    v_seen      BIGINT := 0;
    v_hash      BIGINT := 0;
    v_count     INT    := 0;
BEGIN
    FOR rec IN SELECT schema_name FROM public.domains WHERE is_active = true ORDER BY schema_name
    LOOP
        v_silo := rec.schema_name;

        EXECUTE format(
            $$
            SELECT
                COALESCE(COUNT(*),0),
                COALESCE(SUM(CASE WHEN content_hash IS NOT NULL THEN 1::BIGINT ELSE 0 END),0),
                COALESCE((
                    SELECT COUNT(*) FROM (
                        SELECT url FROM %I.articles WHERE enrichment_status != 'failed'
                        GROUP BY url HAVING COUNT(*) > 1
                    ) x
                ),0),
                COALESCE((
                    SELECT COUNT(*) FROM (
                        SELECT content_hash FROM %I.articles
                        WHERE content_hash IS NOT NULL AND enrichment_status != 'failed'
                        GROUP BY content_hash HAVING COUNT(*) > 1
                    ) y
                ),0)
            FROM %I.articles
            $$, v_silo, v_silo, v_silo
        ) INTO v_seen, v_hash, v_url_dup, v_ch_dup;

        INSERT INTO intelligence.dedup_metrics (silo, metric_date, articles_seen, articles_with_hash, url_duplicates, content_hash_duplicates, last_run_at)
        VALUES (v_silo, p_date, v_seen, v_hash, v_url_dup, v_ch_dup, NOW())
        ON CONFLICT (silo, metric_date) DO UPDATE SET
            articles_seen          = EXCLUDED.articles_seen,
            articles_with_hash     = EXCLUDED.articles_with_hash,
            url_duplicates         = EXCLUDED.url_duplicates,
            content_hash_duplicates = EXCLUDED.content_hash_duplicates,
            last_run_at            = NOW();

        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$;

COMMENT ON FUNCTION intelligence.rebuild_daily_dedup_metrics(DATE) IS 'Backfill / recompute daily aggregates for a given date across all active silos.';
