-- Add status column to intelligence.extracted_claims if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'intelligence' AND table_name = 'extracted_claims' AND column_name = 'status') THEN
        ALTER TABLE intelligence.extracted_claims ADD COLUMN status TEXT NOT NULL DEFAULT 'processed';
    END IF;
END $$;

-- Update existing rows to have status 'processed' (already default, but just in case)
UPDATE intelligence.extracted_claims SET status = 'processed' WHERE status IS NULL;

-- Create index on status for querying unseeded claims
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'intelligence' AND tablename = 'extracted_claims' AND indexname = 'idx_extracted_claims_status') THEN
        CREATE INDEX idx_extracted_claims_status ON intelligence.extracted_claims (status);
    END IF;
END $$;