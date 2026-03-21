-- Migration 138: Article Entity & Event Full-System
-- Structured entity storage at intake: people, orgs, subjects, recurring events
-- Separate storage for dates, times, countries (excluded from topic clustering)
-- Entity canonical/alias support for storyline merge
-- See docs/ARTICLE_ENTITY_SCHEMA_DESIGN.md

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT domains.schema_name FROM domains WHERE is_active = true
    LOOP
        -- 1. entity_canonical (must exist before article_entities due to FK)
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

        -- 2. article_entities (people, orgs, subjects, recurring events)
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

        -- 3. article_extracted_dates (excluded from topic clustering)
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.article_extracted_dates (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES %I.articles(id) ON DELETE CASCADE,
                raw_expression TEXT NOT NULL,
                normalized_date DATE,
                expression_type VARCHAR(30) DEFAULT ''absolute'' CHECK (expression_type IN (
                    ''absolute'', ''relative'', ''period'', ''range'', ''unknown''
                )),
                context_sentence TEXT,
                confidence DECIMAL(3,2) DEFAULT 0.7 CHECK (confidence >= 0.0 AND confidence <= 1.0),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_dates_article ON %I.article_extracted_dates(article_id)', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_dates_normalized ON %I.article_extracted_dates(normalized_date)', schema_name, schema_name);

        -- 4. article_extracted_times (excluded from topic clustering)
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.article_extracted_times (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES %I.articles(id) ON DELETE CASCADE,
                raw_expression TEXT NOT NULL,
                normalized_time TIME,
                timezone VARCHAR(50),
                context_sentence TEXT,
                confidence DECIMAL(3,2) DEFAULT 0.7 CHECK (confidence >= 0.0 AND confidence <= 1.0),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_times_article ON %I.article_extracted_times(article_id)', schema_name, schema_name);

        -- 5. article_extracted_countries (excluded from topic clustering)
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.article_extracted_countries (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES %I.articles(id) ON DELETE CASCADE,
                country_name VARCHAR(255) NOT NULL,
                iso_code CHAR(2),
                mention_context VARCHAR(20) DEFAULT ''body'' CHECK (mention_context IN (''headline'', ''body'')),
                confidence DECIMAL(3,2) DEFAULT 0.8 CHECK (confidence >= 0.0 AND confidence <= 1.0),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, country_name)
            )', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_countries_article ON %I.article_extracted_countries(article_id)', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_countries_name ON %I.article_extracted_countries(LOWER(country_name))', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_countries_iso ON %I.article_extracted_countries(iso_code)', schema_name, schema_name);

        -- 6. article_keywords (thematic only; no dates/times/countries)
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.article_keywords (
                id SERIAL PRIMARY KEY,
                article_id INTEGER NOT NULL REFERENCES %I.articles(id) ON DELETE CASCADE,
                keyword VARCHAR(255) NOT NULL,
                keyword_type VARCHAR(30) DEFAULT ''general'' CHECK (keyword_type IN (
                    ''general'', ''subject'', ''product'', ''technology''
                )),
                source VARCHAR(20) DEFAULT ''body'' CHECK (source IN (''headline'', ''body'', ''both'')),
                confidence DECIMAL(3,2) DEFAULT 0.7 CHECK (confidence >= 0.0 AND confidence <= 1.0),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(article_id, keyword)
            )', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_keywords_article ON %I.article_keywords(article_id)', schema_name, schema_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_article_keywords_keyword ON %I.article_keywords(LOWER(keyword))', schema_name, schema_name);

        -- Comments
        EXECUTE format('COMMENT ON TABLE %I.article_entities IS %L', schema_name, 'Parsed entities per article: people, orgs, subjects, recurring events. Used for storylines and search. Excludes dates/times/countries.');
        EXECUTE format('COMMENT ON TABLE %I.article_extracted_dates IS %L', schema_name, 'Dates mentioned in article. Stored separately; excluded from topic clustering.');
        EXECUTE format('COMMENT ON TABLE %I.article_extracted_times IS %L', schema_name, 'Times mentioned in article. Stored separately; excluded from topic clustering.');
        EXECUTE format('COMMENT ON TABLE %I.article_extracted_countries IS %L', schema_name, 'Countries mentioned in article. Stored separately; excluded from topic clustering.');
        EXECUTE format('COMMENT ON TABLE %I.entity_canonical IS %L', schema_name, 'Canonical entity forms for merging aliases (e.g. Fed -> Federal Reserve).');
        EXECUTE format('COMMENT ON TABLE %I.article_keywords IS %L', schema_name, 'Thematic keywords per article. Excludes dates, times, countries.');

        RAISE NOTICE 'Migration 138: Created article entity tables for schema: %', schema_name;
    END LOOP;
END $$;
