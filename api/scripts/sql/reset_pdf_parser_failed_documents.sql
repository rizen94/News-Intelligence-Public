-- Re-queue processed_documents that failed with missing PDF stack (pdfplumber / pdfminer).
-- Matches by error text — includes rows that never got permanent_failure set (common on Widow).
--
-- Run:
--   PGPASSWORD=... psql -h HOST -p 5432 -U newsapp -d news_intel -v ON_ERROR_STOP=1 -f reset_pdf_parser_failed_documents.sql
--
-- Via SSH to Widow (example):
--   cat api/scripts/sql/reset_pdf_parser_failed_documents.sql | ssh pete@192.168.93.101 \
--     "psql -h 127.0.0.1 -U newsapp -d news_intel -v ON_ERROR_STOP=1"

BEGIN;

SELECT id, title,
  (metadata->'processing'->>'permanent_failure') AS was_permanent,
  LEFT(metadata->'processing'->>'error', 90) AS err
FROM intelligence.processed_documents
WHERE COALESCE(metadata->'processing'->>'error', '') ILIKE '%no pdf parser%'
   OR COALESCE(metadata->'processing'->>'error', '') ILIKE '%install pdfplumber%'
ORDER BY id;

UPDATE intelligence.processed_documents
SET
  metadata = jsonb_set(
    COALESCE(metadata, '{}'::jsonb),
    '{processing}',
    (COALESCE(metadata->'processing', '{}'::jsonb) - 'permanent_failure' - 'error')
    || jsonb_build_object(
      'attempts',
      0,
      'retry_reset_reason',
      'pdf_parser_dependencies_installed_sql'
    )
  ),
  updated_at = NOW()
WHERE COALESCE(metadata->'processing'->>'error', '') ILIKE '%no pdf parser%'
   OR COALESCE(metadata->'processing'->>'error', '') ILIKE '%install pdfplumber%';

COMMIT;
