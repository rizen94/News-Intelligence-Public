-- Migration 193: article_topic_clusters for optional domain silos (artificial_intelligence, medicine, legal).
-- Silo migrations 180/187/188 called create_domain_table for topic_clusters but omitted article_topic_clusters.
-- GET /api/{domain}/content_analysis/topics joins {schema}.article_topic_clusters — without it Route Supervisor
-- and the UI error with "relation ... article_topic_clusters does not exist".
-- Idempotent: create_domain_table is safe to re-run; FK/index/trigger helpers are defensive in newer migrations.

SELECT public.create_domain_table('artificial_intelligence', 'article_topic_clusters', 'science_tech');
SELECT public.create_domain_table('medicine', 'article_topic_clusters', 'science_tech');
SELECT public.create_domain_table('legal', 'article_topic_clusters', 'science_tech');

SELECT public.add_domain_foreign_keys('artificial_intelligence');
SELECT public.add_domain_foreign_keys('medicine');
SELECT public.add_domain_foreign_keys('legal');

SELECT public.create_domain_indexes('artificial_intelligence');
SELECT public.create_domain_indexes('medicine');
SELECT public.create_domain_indexes('legal');

SELECT public.create_domain_triggers('artificial_intelligence');
SELECT public.create_domain_triggers('medicine');
SELECT public.create_domain_triggers('legal');

DO $$
BEGIN
  RAISE NOTICE 'Migration 193: article_topic_clusters ensured for artificial_intelligence, medicine, legal';
END $$;
