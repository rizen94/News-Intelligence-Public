-- Create table for unseeded claims parking lot
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'intelligence' AND table_name = 'unseeded_claims_parking_lot') THEN
        CREATE TABLE intelligence.unseeded_claims_parking_lot (
            id SERIAL PRIMARY KEY,
            context_id INTEGER NOT NULL,
            subject_text TEXT NOT NULL,
            predicate_text TEXT NOT NULL,
            object_text TEXT,
            confidence REAL NOT NULL,
            extracted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            domain_key TEXT,
            retry_count INTEGER DEFAULT 0,
            last_retry_at TIMESTAMP WITH TIME ZONE,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'reviewed', 'dismissed')),
            UNIQUE(context_id, subject_text, predicate_text, object_text)
        );
    END IF;
END $$;

-- Create indexes for performance
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'intelligence' AND tablename = 'unseeded_claims_parking_lot' AND indexname = 'idx_unseeded_claims_context_id') THEN
        CREATE INDEX idx_unseeded_claims_context_id ON intelligence.unseeded_claims_parking_lot (context_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'intelligence' AND tablename = 'unseeded_claims_parking_lot' AND indexname = 'idx_unseeded_claims_status') THEN
        CREATE INDEX idx_unseeded_claims_status ON intelligence.unseeded_claims_parking_lot (status);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname = 'intelligence' AND tablename = 'unseeded_claims_parking_lot' AND indexname = 'idx_unseeded_claims_domain_key') THEN
        CREATE INDEX idx_unseeded_claims_domain_key ON intelligence.unseeded_claims_parking_lot (domain_key);
    END IF;
END $$;