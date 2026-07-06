-- News Intelligence Kit baseline schema (no active user domains).
-- Domain silos provisioned at setup via kit_provision_domain().

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS intelligence;
CREATE SCHEMA IF NOT EXISTS template_silo;

-- Domains catalog
CREATE TABLE IF NOT EXISTS public.domains (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    schema_name VARCHAR(63) NOT NULL,
    display_order INTEGER DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.domain_metadata (
    domain_id INTEGER PRIMARY KEY REFERENCES public.domains(id) ON DELETE CASCADE,
    article_count INTEGER DEFAULT 0,
    topic_count INTEGER DEFAULT 0,
    storyline_count INTEGER DEFAULT 0,
    feed_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.automation_state (
    key VARCHAR(128) PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.automation_run_history (
    id BIGSERIAL PRIMARY KEY,
    phase_name VARCHAR(128) NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    success BOOLEAN,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_automation_run_history_phase
    ON public.automation_run_history (phase_name, finished_at DESC);

-- Intelligence global tables (minimal kit subset)
CREATE TABLE IF NOT EXISTS intelligence.contexts (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50),
    title TEXT,
    body TEXT,
    source_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS intelligence.entity_profiles (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50),
    canonical_entity_id INTEGER,
    display_name TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence.chronological_events (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50),
    title TEXT NOT NULL,
    description TEXT,
    event_date TIMESTAMPTZ,
    canonical_event_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence.extracted_claims (
    id BIGSERIAL PRIMARY KEY,
    context_id INTEGER REFERENCES intelligence.contexts(id) ON DELETE CASCADE,
    subject TEXT,
    claim_text TEXT,
    confidence REAL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence.versioned_facts (
    id BIGSERIAL PRIMARY KEY,
    domain_key VARCHAR(50),
    subject TEXT,
    fact_text TEXT,
    confidence REAL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence.content_refinement_queue (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER,
    domain_key VARCHAR(50),
    status VARCHAR(32) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence.graph_connection_proposals (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(64),
    source_id TEXT,
    target_type VARCHAR(64),
    target_id TEXT,
    relationship TEXT,
    confidence REAL,
    status VARCHAR(32) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Template silo tables (clone source for new domains)
CREATE TABLE IF NOT EXISTS template_silo.articles (
    id SERIAL PRIMARY KEY,
    title TEXT,
    url TEXT UNIQUE,
    content TEXT,
    summary TEXT,
    author TEXT,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    processing_status VARCHAR(32) DEFAULT 'pending',
    enrichment_status VARCHAR(32),
    sentiment_score REAL,
    metadata JSONB DEFAULT '{}'::jsonb,
    ml_processed BOOLEAN DEFAULT FALSE,
    timeline_processed BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS template_silo.topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_silo.storylines (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS template_silo.rss_feeds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    url TEXT NOT NULL UNIQUE,
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS template_silo.article_topic_assignments (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES template_silo.articles(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES template_silo.topics(id) ON DELETE CASCADE,
    confidence REAL,
    UNIQUE (article_id, topic_id)
);

CREATE TABLE IF NOT EXISTS template_silo.storyline_articles (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER REFERENCES template_silo.storylines(id) ON DELETE CASCADE,
    article_id INTEGER REFERENCES template_silo.articles(id) ON DELETE CASCADE,
    UNIQUE (storyline_id, article_id)
);

CREATE TABLE IF NOT EXISTS template_silo.entity_canonical (
    id SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    entity_type VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS template_silo.article_entities (
    id SERIAL PRIMARY KEY,
    article_id INTEGER REFERENCES template_silo.articles(id) ON DELETE CASCADE,
    canonical_entity_id INTEGER REFERENCES template_silo.entity_canonical(id) ON DELETE SET NULL,
    entity_name TEXT,
    entity_type VARCHAR(50)
);

-- Provision new domain schema from template_silo
CREATE OR REPLACE FUNCTION public.kit_provision_domain(
    p_domain_key TEXT,
    p_schema_name TEXT,
    p_display_name TEXT,
    p_description TEXT DEFAULT ''
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF p_schema_name !~ '^[a-z][a-z0-9_]*$' THEN
        RAISE EXCEPTION 'invalid schema_name: %', p_schema_name;
    END IF;
    IF p_domain_key !~ '^[a-z0-9-]+$' THEN
        RAISE EXCEPTION 'invalid domain_key: %', p_domain_key;
    END IF;

    INSERT INTO public.domains (domain_key, name, schema_name, description, is_active)
    VALUES (p_domain_key, p_display_name, p_schema_name, p_description, TRUE)
    ON CONFLICT (domain_key) DO UPDATE SET
        name = EXCLUDED.name,
        schema_name = EXCLUDED.schema_name,
        description = EXCLUDED.description,
        is_active = TRUE;

    INSERT INTO public.domain_metadata (domain_id, article_count, topic_count, storyline_count, feed_count)
    SELECT d.id, 0, 0, 0, 0 FROM public.domains d WHERE d.domain_key = p_domain_key
    ON CONFLICT (domain_id) DO NOTHING;

    EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', p_schema_name);

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.articles (LIKE template_silo.articles INCLUDING ALL)',
        p_schema_name
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.topics (LIKE template_silo.topics INCLUDING ALL)',
        p_schema_name
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.storylines (LIKE template_silo.storylines INCLUDING ALL)',
        p_schema_name
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.rss_feeds (LIKE template_silo.rss_feeds INCLUDING ALL)',
        p_schema_name
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.article_topic_assignments (LIKE template_silo.article_topic_assignments INCLUDING ALL)',
        p_schema_name
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.storyline_articles (LIKE template_silo.storyline_articles INCLUDING ALL)',
        p_schema_name
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.entity_canonical (LIKE template_silo.entity_canonical INCLUDING ALL)',
        p_schema_name
    );
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I.article_entities (LIKE template_silo.article_entities INCLUDING ALL)',
        p_schema_name
    );
END;
$$;

INSERT INTO public.automation_state (key, value) VALUES
    ('setup_complete', 'false'::jsonb),
    ('kit_schema_version', '"1"'::jsonb)
ON CONFLICT (key) DO NOTHING;
