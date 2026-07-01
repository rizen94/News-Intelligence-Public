-- Migration 244: topic_keywords + cluster search indexes + mv_topic_index for all active domain silos.
-- Silo migrations 180/187/188 created topic_clusters but omitted topic_keywords on legal/medicine/AI.
-- Idempotent: create_domain_table + IF NOT EXISTS indexes / matviews.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
DECLARE
    sch text;
BEGIN
    FOR sch IN
        SELECT schema_name FROM public.domains WHERE is_active ORDER BY schema_name
    LOOP
        IF to_regclass(format('%I.topic_clusters', sch)) IS NULL THEN
            RAISE NOTICE '244: skip % — no topic_clusters', sch;
            CONTINUE;
        END IF;

        PERFORM public.create_domain_table(sch, 'topic_keywords', 'politics');
        PERFORM public.create_domain_table(sch, 'article_topic_clusters', 'science_tech');

        BEGIN
            PERFORM public.add_domain_foreign_keys(sch);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE '244: add_domain_foreign_keys %: %', sch, SQLERRM;
        END;
        BEGIN
            PERFORM public.create_domain_indexes(sch);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE '244: create_domain_indexes %: %', sch, SQLERRM;
        END;
        BEGIN
            PERFORM public.create_domain_triggers(sch);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE '244: create_domain_triggers %: %', sch, SQLERRM;
        END;

        IF to_regclass(format('%I.topic_clusters', sch)) IS NOT NULL THEN
            BEGIN
                EXECUTE format(
                    'CREATE INDEX IF NOT EXISTS idx_%I_topic_clusters_name_trgm ON %I.topic_clusters USING gin (lower(cluster_name) gin_trgm_ops)',
                    sch, sch
                );
            EXCEPTION WHEN duplicate_table THEN
                NULL;
            END;
        END IF;

        IF to_regclass(format('%I.topic_keywords', sch)) IS NOT NULL THEN
            BEGIN
                EXECUTE format(
                    'CREATE INDEX IF NOT EXISTS idx_%I_topic_keywords_cluster_keyword ON %I.topic_keywords (topic_cluster_id, lower(keyword))',
                    sch, sch
                );
            EXCEPTION WHEN duplicate_table THEN
                NULL;
            END;
        END IF;

        IF to_regclass(format('%I.mv_topic_index', sch)) IS NULL
           AND to_regclass(format('%I.topic_keywords', sch)) IS NOT NULL THEN
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

        RAISE NOTICE '244: topic cluster index stack ensured for %', sch;
    END LOOP;
END $$;
