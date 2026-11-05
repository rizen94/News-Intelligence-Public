-- Migration 249: Home feed storyline status + timestamp scan optimization
-- Fills two coverage gaps in _fetch_candidate_rows (reader/services/home_feed.py):
--   Gap 1 - status exclusion forces post-filter on ~30% of unmerged rows
--   Gap 2 - last_refinement has no index (BitmapOr/SeqScan fallback)
-- Note: storyline_articles.last_article_added_at is NOT a column — it is the
--       aggregate alias MAX(sa.added_at). The M239 index
--       idx_*_sa_storyline_added_at ON (storyline_id, added_at DESC) covers
--       the LATERAL EXISTS clause (line 719-724 in home_feed.py).

DO $$
DECLARE
    rec RECORD;
    schema_name TEXT;
BEGIN
    -- Iterate over every active domain (politics, finance, etc.)
    FOR rec IN
        SELECT d.domain_key, d.schema_name
          FROM public.domains d
         WHERE d.is_active = true
         ORDER BY d.domain_key
    LOOP
        schema_name := rec.schema_name;

        -- Index 1: composite status → timeline
        EXECUTE format(
            $sql$CREATE INDEX CONCURRENTLY IF NOT EXISTS
                idx_%I_storylines_status_timeline ON %I.storylines (status, updated_at DESC NULLS LAST)
                WHERE merged_into_id IS NULL$sql$,
            schema_name,
            schema_name
        );

        -- Index 2: last_refinement standalone btree
        EXECUTE format(
            $sql$CREATE INDEX CONCURRENTLY IF NOT EXISTS
                idx_%I_storylines_last_refinement ON %I.storylines (last_refinement DESC NULLS LAST)$sql$,
            schema_name,
            schema_name
        );

    END LOOP;

    RAISE NOTICE 'Migration 249: home feed storyline indexes ensured for active domain schemas';
END $$;
