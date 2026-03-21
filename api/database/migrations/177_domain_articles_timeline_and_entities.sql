-- Migration 177: Per-domain articles.timeline_processed + ensure entity_canonical / article_entities
-- Fixes event_extraction / timeline gating that expects timeline_processed on domain articles.
-- Idempotent: safe if migration 138 already ran (CREATE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT d.schema_name FROM public.domains d WHERE d.is_active = true
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.articles ADD COLUMN IF NOT EXISTS timeline_processed BOOLEAN DEFAULT false',
            schema_name
        );
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%I_articles_timeline_processed ON %I.articles(timeline_processed)',
            schema_name,
            schema_name
        );

        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.entity_canonical (
                id SERIAL PRIMARY KEY,
                canonical_name VARCHAR(255) NOT NULL,
                entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
                    ''person'', ''organization'', ''subject'', ''recurring_event''
                )),
                aliases TEXT[] DEFAULT ''{}'',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(canonical_name, entity_type)
            )', schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_entity_canonical_name ON %I.entity_canonical (LOWER(canonical_name))', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_entity_canonical_aliases ON %I.entity_canonical USING GIN(aliases)', schema_name, schema_name);

        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.article_entities (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES %I.articles(id) ON DELETE CASCADE,
                entity_name VARCHAR(255) NOT NULL,
                entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
                    ''person'', ''organization'', ''subject'', ''recurring_event''
                )),
                mention_source VARCHAR(20) DEFAULT ''body'' CHECK (mention_source IN (''headline'', ''body'', ''both'')),
                confidence DECIMAL(3,2) DEFAULT 0.8 CHECK (confidence >= 0.0 AND confidence <= 1.0),
                canonical_entity_id INTEGER REFERENCES %I.entity_canonical(id) ON DELETE SET NULL,
                source_text_snippet TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, entity_name, entity_type)
            )', schema_name, schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_entities_article ON %I.article_entities(article_id)', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_entities_entity ON %I.article_entities(LOWER(entity_name), entity_type)', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_entities_type ON %I.article_entities(entity_type)', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_entities_canonical ON %I.article_entities(canonical_entity_id)', schema_name, schema_name);

        RAISE NOTICE 'Migration 177: timeline_processed + entity tables ensured for schema %', schema_name;
    END LOOP;
END $$;
