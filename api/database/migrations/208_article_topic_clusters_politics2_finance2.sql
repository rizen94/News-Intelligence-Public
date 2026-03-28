-- Migration 208: article_topic_clusters for template silos politics_2 / finance_2.
-- Migration 201 created topic_clusters (and related) but omitted article_topic_clusters, same gap as
-- optional silos fixed in 193. GET /api/{domain}/content_analysis/topics joins {schema}.article_topic_clusters.
-- Idempotent: create_domain_table is safe to re-run.

SELECT public.create_domain_table('politics_2', 'article_topic_clusters', 'science_tech');
SELECT public.create_domain_table('finance_2', 'article_topic_clusters', 'science_tech');

SELECT public.add_domain_foreign_keys('politics_2');
SELECT public.add_domain_foreign_keys('finance_2');

SELECT public.create_domain_indexes('politics_2');
SELECT public.create_domain_indexes('finance_2');

SELECT public.create_domain_triggers('politics_2');
SELECT public.create_domain_triggers('finance_2');

DO $$
BEGIN
  RAISE NOTICE 'Migration 208: article_topic_clusters ensured for politics_2, finance_2';
END $$;
