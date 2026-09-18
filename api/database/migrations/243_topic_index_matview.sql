-- Migration 243: materialized topic index per active domain (REFRESH CONCURRENTLY)
-- Original apply loop: politics/finance only. Superseded for all domains by 244/245 on Widow.

DO $$
DECLARE
    sch text;
BEGIN
    FOREACH sch IN ARRAY ARRAY['politics', 'finance'] LOOP
        IF to_regclass(sch || '.topic_clusters') IS NULL THEN
            CONTINUE;
        END IF;

        IF to_regclass(format('%I.mv_topic_index', sch)) IS NULL THEN
            EXECUTE format($mv$
                CREATE MATERIALIZED VIEW %I.mv_topic_index AS
                SELECT
                    tc.id AS cluster_id,
                    tc.cluster_name,
                    COALESCE(tc.article_count, 0) AS article_count,
                    COALESCE(tc.relevance_score, 0.5) AS relevance_score,
                    (
                        SELECT array_agg(tk.keyword ORDER BY tk.importance_score DESC, tk.frequency_count DESC)
                        FROM (
                            SELECT keyword, importance_score, frequency_count
                            FROM %I.topic_keywords
                            WHERE topic_cluster_id = tc.id
                            ORDER BY importance_score DESC, frequency_count DESC
                            LIMIT 12
                        ) tk
                    ) AS top_keywords,
                    tc.updated_at AS last_updated
                FROM %I.topic_clusters tc
            $mv$, sch, sch, sch);
        END IF;

        IF to_regclass(format('%I.mv_topic_index', sch)) IS NOT NULL THEN
            EXECUTE format(
                'CREATE UNIQUE INDEX IF NOT EXISTS idx_%I_mv_topic_index_cluster_id ON %I.mv_topic_index (cluster_id)',
                sch, sch
            );
        END IF;
    END LOOP;
END $$;
