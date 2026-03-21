-- Migration 175: Bootstrap public.chronological_events for domain-silo databases
-- where 060 was never applied or cannot run (FK/views reference public.articles).
--
-- - Creates public.chronological_events without FK to articles (article IDs are per-domain).
-- - Adds v5 columns and indexes aligned with 133_event_extraction_v5.sql.
-- - Applies storyline lifecycle columns/constraints per active domain (158-style loop),
--   plus public.storylines when that table still exists.
-- - Includes core indexes, check constraints, and sequence trigger from 060 (no views
--   that JOIN public.articles; no deduplication_log insert).

-- =============================================================================
-- 1. Core table (060 structure, no FK to articles)
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.chronological_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    storyline_id VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    event_type VARCHAR(100) DEFAULT 'general',
    actual_event_date DATE,
    actual_event_time TIME,
    relative_temporal_expression TEXT,
    temporal_confidence NUMERIC(3,2) DEFAULT 0.0,
    historical_context TEXT,
    related_events JSONB DEFAULT '[]'::jsonb,
    event_sequence_position INTEGER,
    source_article_id INTEGER NOT NULL,
    source_text TEXT,
    source_paragraph INTEGER,
    source_sentence_start INTEGER,
    source_sentence_end INTEGER,
    extraction_method VARCHAR(50) DEFAULT 'ml',
    extraction_confidence NUMERIC(3,2) DEFAULT 0.0,
    extraction_model VARCHAR(100),
    extraction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    importance_score NUMERIC(3,2) DEFAULT 0.0,
    impact_level VARCHAR(50) DEFAULT 'medium',
    location VARCHAR(255),
    entities JSONB DEFAULT '[]'::jsonb,
    tags TEXT[] DEFAULT '{}',
    verified BOOLEAN DEFAULT FALSE,
    verification_source VARCHAR(255),
    verification_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 2. v5 event extraction columns (133)
-- =============================================================================
ALTER TABLE public.chronological_events
ADD COLUMN IF NOT EXISTS event_fingerprint VARCHAR(128),
ADD COLUMN IF NOT EXISTS canonical_event_id INTEGER REFERENCES public.chronological_events(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS source_count INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS last_corroborated_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS key_actors JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS outcome TEXT,
ADD COLUMN IF NOT EXISTS is_ongoing BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS continuation_signals JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS date_precision VARCHAR(20) DEFAULT 'unknown';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = 'public' AND t.relname = 'chronological_events'
          AND c.conname = 'chronological_events_date_precision_check'
    ) THEN
        ALTER TABLE public.chronological_events
        ADD CONSTRAINT chronological_events_date_precision_check
        CHECK (date_precision IN ('exact', 'week', 'month', 'quarter', 'year', 'unknown'));
    END IF;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- =============================================================================
-- 3. Indexes (060 + 133)
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_chronological_events_storyline_id ON public.chronological_events(storyline_id);
CREATE INDEX IF NOT EXISTS idx_chronological_events_actual_date ON public.chronological_events(actual_event_date);
CREATE INDEX IF NOT EXISTS idx_chronological_events_type ON public.chronological_events(event_type);
CREATE INDEX IF NOT EXISTS idx_chronological_events_importance ON public.chronological_events(importance_score);
CREATE INDEX IF NOT EXISTS idx_chronological_events_sequence ON public.chronological_events(event_sequence_position);
CREATE INDEX IF NOT EXISTS idx_chronological_events_source_article ON public.chronological_events(source_article_id);
CREATE INDEX IF NOT EXISTS idx_chronological_events_extraction_method ON public.chronological_events(extraction_method);

CREATE INDEX IF NOT EXISTS idx_chrono_events_fingerprint ON public.chronological_events (event_fingerprint);
CREATE INDEX IF NOT EXISTS idx_chrono_events_canonical ON public.chronological_events (canonical_event_id);
CREATE INDEX IF NOT EXISTS idx_chrono_events_event_type ON public.chronological_events (event_type);
CREATE INDEX IF NOT EXISTS idx_chrono_events_actual_date ON public.chronological_events(actual_event_date);
CREATE INDEX IF NOT EXISTS idx_chrono_events_ongoing ON public.chronological_events (is_ongoing) WHERE is_ongoing = TRUE;
CREATE INDEX IF NOT EXISTS idx_chrono_events_storyline ON public.chronological_events (storyline_id);

-- =============================================================================
-- 4. Check constraints from 060 (idempotent)
-- =============================================================================
DO $$ BEGIN
    ALTER TABLE public.chronological_events ADD CONSTRAINT chk_importance_score CHECK (importance_score >= 0.0 AND importance_score <= 1.0);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.chronological_events ADD CONSTRAINT chk_temporal_confidence CHECK (temporal_confidence >= 0.0 AND temporal_confidence <= 1.0);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.chronological_events ADD CONSTRAINT chk_extraction_confidence CHECK (extraction_confidence >= 0.0 AND extraction_confidence <= 1.0);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- =============================================================================
-- 5. Sequence helper + triggers (060)
-- =============================================================================
CREATE OR REPLACE FUNCTION public.calculate_event_sequence(
    p_storyline_id VARCHAR(255)
) RETURNS VOID AS $$
BEGIN
    UPDATE public.chronological_events
    SET event_sequence_position = subquery.sequence_pos
    FROM (
        SELECT id, ROW_NUMBER() OVER (ORDER BY actual_event_date, actual_event_time) AS sequence_pos
        FROM public.chronological_events
        WHERE storyline_id = p_storyline_id
        AND actual_event_date IS NOT NULL
    ) subquery
    WHERE public.chronological_events.id = subquery.id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.trigger_update_event_sequence()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM public.calculate_event_sequence(NEW.storyline_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_event_sequence ON public.chronological_events;
CREATE TRIGGER trigger_update_event_sequence
    AFTER INSERT OR UPDATE OF actual_event_date, actual_event_time ON public.chronological_events
    FOR EACH ROW EXECUTE FUNCTION public.trigger_update_event_sequence();

CREATE OR REPLACE FUNCTION public.trigger_update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_chronological_events_updated_at ON public.chronological_events;
CREATE TRIGGER trigger_update_chronological_events_updated_at
    BEFORE UPDATE ON public.chronological_events
    FOR EACH ROW EXECUTE FUNCTION public.trigger_update_updated_at();

-- =============================================================================
-- 6. App grants (role may not exist on dev DB — ignore)
-- =============================================================================
DO $$
BEGIN
    GRANT SELECT, INSERT, UPDATE, DELETE ON public.chronological_events TO newsapp;
    GRANT USAGE, SELECT ON SEQUENCE public.chronological_events_id_seq TO newsapp;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Grant to newsapp skipped: %', SQLERRM;
END $$;

-- =============================================================================
-- 7. Storyline lifecycle: per active domain schema (+ public if present)
-- =============================================================================
DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN SELECT d.schema_name FROM public.domains d WHERE d.is_active = true
    LOOP
        EXECUTE format('ALTER TABLE %I.storylines DROP CONSTRAINT IF EXISTS storylines_status_check', schema_name);
        EXECUTE format('ALTER TABLE %I.storylines DROP CONSTRAINT IF EXISTS chk_storyline_status', schema_name);
        EXECUTE format(
            $f$
            ALTER TABLE %I.storylines ADD CONSTRAINT chk_storyline_status CHECK (status IN (
                'draft', 'active', 'dormant', 'watching', 'concluded', 'archived', 'completed', 'failed'
            ))
            $f$,
            schema_name
        );
        EXECUTE format('ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMPTZ', schema_name);
        EXECUTE format('ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS dormant_since TIMESTAMPTZ', schema_name);
        EXECUTE format('ALTER TABLE %I.storylines ADD COLUMN IF NOT EXISTS reactivation_count INTEGER DEFAULT 0', schema_name);
        RAISE NOTICE 'Storyline v5 lifecycle applied: %.storylines', schema_name;
    END LOOP;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'storylines'
    ) THEN
        ALTER TABLE public.storylines DROP CONSTRAINT IF EXISTS storylines_status_check;
        ALTER TABLE public.storylines DROP CONSTRAINT IF EXISTS chk_storyline_status;
        ALTER TABLE public.storylines ADD CONSTRAINT chk_storyline_status CHECK (status IN (
            'draft', 'active', 'dormant', 'watching', 'concluded', 'archived', 'completed', 'failed'
        ));
        ALTER TABLE public.storylines
            ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS dormant_since TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS reactivation_count INTEGER DEFAULT 0;
        RAISE NOTICE 'Storyline v5 lifecycle applied: public.storylines';
    END IF;
END $$;

COMMENT ON TABLE public.chronological_events IS 'Extracted timeline events (global). source_article_id refers to domain articles; no single-table FK (domain silos).';
