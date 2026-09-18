-- Migration 242: pg_trgm indexes for topic_clusters search + topic_keywords lookup
-- Original apply loop: politics/finance only. Superseded for all domains by 244/245 on Widow.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
DECLARE
    sch text;
BEGIN
    FOREACH sch IN ARRAY ARRAY['politics', 'finance'] LOOP
        IF to_regclass(sch || '.topic_clusters') IS NOT NULL THEN
            BEGIN
                EXECUTE format(
                    'CREATE INDEX IF NOT EXISTS idx_%I_topic_clusters_name_trgm ON %I.topic_clusters USING gin (lower(cluster_name) gin_trgm_ops)',
                    sch, sch
                );
            EXCEPTION WHEN duplicate_table THEN
                NULL;
            END;
        END IF;
        IF to_regclass(sch || '.topic_keywords') IS NOT NULL THEN
            BEGIN
                EXECUTE format(
                    'CREATE INDEX IF NOT EXISTS idx_%I_topic_keywords_cluster_keyword ON %I.topic_keywords (topic_cluster_id, lower(keyword))',
                    sch, sch
                );
            EXCEPTION WHEN duplicate_table THEN
                NULL;
            END;
        END IF;
    END LOOP;
END $$;
