-- Migration 268: Align article_topic_clusters FK column with writers.
-- politics/finance (and any older silo) used cluster_id + confidence.
-- Discovery, topic clustering, and signal-first SQL expect topic_cluster_id +
-- confidence_score / relevance_score (science_tech / AI / medicine shape).
--
-- Symptom: Storyline discovery failed for politics/finance:
--   column atc.topic_cluster_id does not exist
-- Date: 2026-11-12

BEGIN;

DO $$
DECLARE
  sch text;
BEGIN
  FOR sch IN
    SELECT DISTINCT c.table_schema
    FROM information_schema.columns c
    WHERE c.table_name = 'article_topic_clusters'
      AND c.table_schema NOT IN ('pg_catalog', 'information_schema', 'public')
  LOOP
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = sch AND table_name = 'article_topic_clusters'
        AND column_name = 'cluster_id'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = sch AND table_name = 'article_topic_clusters'
        AND column_name = 'topic_cluster_id'
    ) THEN
      EXECUTE format(
        'ALTER TABLE %I.article_topic_clusters RENAME COLUMN cluster_id TO topic_cluster_id',
        sch
      );
    END IF;

    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = sch AND table_name = 'article_topic_clusters'
        AND column_name = 'confidence'
    ) AND NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = sch AND table_name = 'article_topic_clusters'
        AND column_name = 'confidence_score'
    ) THEN
      EXECUTE format(
        'ALTER TABLE %I.article_topic_clusters RENAME COLUMN confidence TO confidence_score',
        sch
      );
    END IF;

    EXECUTE format(
      'ALTER TABLE %I.article_topic_clusters ADD COLUMN IF NOT EXISTS relevance_score DOUBLE PRECISION',
      sch
    );
    EXECUTE format(
      'ALTER TABLE %I.article_topic_clusters ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ DEFAULT NOW()',
      sch
    );
    EXECUTE format(
      'ALTER TABLE %I.article_topic_clusters ADD COLUMN IF NOT EXISTS assignment_method TEXT',
      sch
    );
    EXECUTE format(
      'ALTER TABLE %I.article_topic_clusters ADD COLUMN IF NOT EXISTS metadata JSONB',
      sch
    );
    EXECUTE format(
      'UPDATE %I.article_topic_clusters SET relevance_score = COALESCE(relevance_score, confidence_score, 0) WHERE relevance_score IS NULL',
      sch
    );
  END LOOP;
END $$;

COMMIT;
