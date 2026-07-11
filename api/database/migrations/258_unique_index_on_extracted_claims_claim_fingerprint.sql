-- Add claim_fingerprint column to intelligence.extracted_claims if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'intelligence' AND table_name = 'extracted_claims' AND column_name = 'claim_fingerprint') THEN
        ALTER TABLE intelligence.extracted_claims ADD COLUMN claim_fingerprint TEXT;
    END IF;
END $$;

-- Update existing rows with a fingerprint based on context_id, subject_text, predicate_text, object_text
UPDATE intelligence.extracted_claims
SET claim_fingerprint = substring(
    sha256(
        (context_id::text) || '::' ||
        coalesce(lower(regexp_replace(subject_text, '\s+', ' ', 'g')), '') || '::' ||
        coalesce(lower(regexp_replace(predicate_text, '\s+', ' ', 'g')), '') || '::' ||
        coalesce(lower(regexp_replace(object_text, '\s+', ' ', 'g')), '')
    ) from 1 for 64
) WHERE claim_fingerprint IS NULL;

-- Make the column non-nullable (assuming all rows now have a value)
ALTER TABLE intelligence.extracted_claims ALTER COLUMN claim_fingerprint SET NOT NULL;

-- Create unique index on claim_fingerprint
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'intelligence' AND tablename = 'extracted_claims' AND indexname = 'ux_extracted_claims_claim_fingerprint') THEN
        CREATE UNIQUE INDEX ux_extracted_claims_claim_fingerprint ON intelligence.extracted_claims (claim_fingerprint);
    END IF;
END $$;