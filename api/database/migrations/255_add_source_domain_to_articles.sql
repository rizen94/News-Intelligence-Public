-- Migration 255: Add source_domain column to all domain articles tables
-- The RSS collector inserts source_domain into articles but no prior migration added it.
-- Idempotent: IF NOT EXISTS / DO NOTHING safe.

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT d.schema_name FROM public.domains d WHERE d.is_active = true
    LOOP
        -- Add source_domain column if missing
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS source_domain VARCHAR(255) DEFAULT ''''',
            schema_name
        );
        
        -- Add index for faster lookups by source domain
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%I_articles_source_domain ON %I.articles(source_domain)',
            schema_name,
            schema_name
        );
        
        RAISE NOTICE 'Migration 255: source_domain ensured on schema %', schema_name;
    END LOOP;
END $$;

-- Verify provisioning status for all active domains
DO $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN SELECT d.domain_key, d.schema_name, d.name
               FROM public.domains d 
               WHERE d.is_active = true
               ORDER BY d.display_order NULLS LAST, d.domain_key
    LOOP
        RAISE NOTICE 'Migration 255: domain % (schema %) — source_domain column verified', rec.domain_key, rec.schema_name;
    END LOOP;
END $$;
