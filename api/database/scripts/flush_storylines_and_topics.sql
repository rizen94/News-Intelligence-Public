-- Flush all storylines and topics for a clean slate
-- Run per domain schema. Keeps: articles, rss_feeds, banned_topics.
-- Clears: storylines, storyline_articles, topic_clusters, article_topic_clusters, topic_keywords,
--         topic_extraction_queue, chronological_events, etc.

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT domains.schema_name FROM domains WHERE is_active = true
    LOOP
        RAISE NOTICE 'Flushing storylines and topics for schema: %', schema_name;

        -- 1. Storyline article suggestions (references storylines)
        BEGIN
            EXECUTE format('DELETE FROM %I.storyline_article_suggestions', schema_name);
            RAISE NOTICE '  - Deleted storyline_article_suggestions';
        EXCEPTION WHEN undefined_table THEN
            NULL;
        END;

        -- 2. Storyline automation log (references storylines)
        BEGIN
            EXECUTE format('DELETE FROM %I.storyline_automation_log', schema_name);
            RAISE NOTICE '  - Deleted storyline_automation_log';
        EXCEPTION WHEN undefined_table THEN
            NULL;
        END;

        -- 3. Storyline articles (references storylines)
        EXECUTE format('DELETE FROM %I.storyline_articles', schema_name);
        RAISE NOTICE '  - Deleted storyline_articles';

        -- 3b. Timeline events (references storylines) - must run before storylines
        BEGIN
            EXECUTE format('DELETE FROM %I.timeline_events', schema_name);
            RAISE NOTICE '  - Deleted timeline_events';
        EXCEPTION WHEN undefined_table THEN
            NULL;
        END;

        -- 4. Storylines
        EXECUTE format('DELETE FROM %I.storylines', schema_name);
        RAISE NOTICE '  - Deleted storylines';

        -- 5. Topic keywords (references topic_clusters)
        BEGIN
            EXECUTE format('DELETE FROM %I.topic_keywords', schema_name);
            RAISE NOTICE '  - Deleted topic_keywords';
        EXCEPTION WHEN undefined_table THEN
            NULL;
        END;

        -- 6. Article-topic cluster assignments (references topic_clusters)
        EXECUTE format('DELETE FROM %I.article_topic_clusters', schema_name);
        RAISE NOTICE '  - Deleted article_topic_clusters';

        -- 7. Topic clusters
        EXECUTE format('DELETE FROM %I.topic_clusters', schema_name);
        RAISE NOTICE '  - Deleted topic_clusters';

        -- 8. Topic extraction queue (so articles get re-processed)
        BEGIN
            EXECUTE format('DELETE FROM %I.topic_extraction_queue', schema_name);
            RAISE NOTICE '  - Deleted topic_extraction_queue';
        EXCEPTION WHEN undefined_table THEN
            NULL;
        END;

        -- 9. Story entity index (references storylines) - if exists
        BEGIN
            EXECUTE format('DELETE FROM %I.story_entity_index', schema_name);
            RAISE NOTICE '  - Deleted story_entity_index';
        EXCEPTION WHEN undefined_table THEN
            NULL;
        END;

        RAISE NOTICE '  Done with %', schema_name;
    END LOOP;

    -- 10. Public chronological_events (timeline events; no schema prefix = public)
    BEGIN
        TRUNCATE chronological_events CASCADE;
        RAISE NOTICE 'Cleared chronological_events';
    EXCEPTION WHEN undefined_table THEN
        NULL;
    END;

    -- 11. Public watchlist (references storylines - may be domain-scoped via app)
    BEGIN
        DELETE FROM watchlist;
        RAISE NOTICE 'Cleared public.watchlist';
    EXCEPTION WHEN undefined_table THEN
        NULL;
    END;

    -- 12. Public storyline_insights (has storyline_id)
    BEGIN
        DELETE FROM storyline_insights;
        RAISE NOTICE 'Cleared storyline_insights';
    EXCEPTION WHEN undefined_table THEN
        NULL;
    END;

    -- 13. Public storyline_correlations
    BEGIN
        DELETE FROM storyline_correlations;
        RAISE NOTICE 'Cleared storyline_correlations';
    EXCEPTION WHEN undefined_table THEN
        NULL;
    END;

    RAISE NOTICE '========================================';
    RAISE NOTICE 'Flush complete. Run topic clustering to rebuild topics.';
END $$;
