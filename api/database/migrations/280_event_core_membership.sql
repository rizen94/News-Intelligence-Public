-- Migration 280: Event-core membership — TE anchors/particulars/arc_state,
-- TE-first typed article membership, TE↔many storyline facets.
-- Forward-only; does not rewrite existing storyline_articles bags.

ALTER TABLE intelligence.tracked_events
    ADD COLUMN IF NOT EXISTS anchors JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS particulars JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS arc_state TEXT NOT NULL DEFAULT 'emerging';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'tracked_events_arc_state_check'
    ) THEN
        ALTER TABLE intelligence.tracked_events
            ADD CONSTRAINT tracked_events_arc_state_check
            CHECK (arc_state IN ('emerging', 'active', 'dormant', 'resolved'));
    END IF;
END $$;

COMMENT ON COLUMN intelligence.tracked_events.anchors IS
    'Curated distinctive anchors (rare names / instrument IDs). Owned match surface for event-core.';
COMMENT ON COLUMN intelligence.tracked_events.particulars IS
    'Contradictable event particulars (pathogen, vector, region, window, court, …).';
COMMENT ON COLUMN intelligence.tracked_events.arc_state IS
    'Episode lifecycle: emerging | active | dormant | resolved.';

CREATE TABLE IF NOT EXISTS intelligence.event_article_membership (
    id BIGSERIAL PRIMARY KEY,
    tracked_event_id BIGINT NOT NULL
        REFERENCES intelligence.tracked_events (id) ON DELETE CASCADE,
    domain_key TEXT NOT NULL,
    article_id BIGINT NOT NULL,
    membership_type TEXT NOT NULL,
    anchor_ref TEXT NOT NULL,
    facet TEXT,
    added_by TEXT NOT NULL DEFAULT 'event_core',
    grounds JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT event_article_membership_type_check CHECK (
        membership_type IN (
            'same_event',
            'causal_link',
            'same_instrument',
            'actor_episode'
        )
    ),
    CONSTRAINT uq_event_article_membership
        UNIQUE (tracked_event_id, domain_key, article_id)
);

CREATE INDEX IF NOT EXISTS idx_event_article_membership_article
    ON intelligence.event_article_membership (domain_key, article_id);

CREATE INDEX IF NOT EXISTS idx_event_article_membership_anchor
    ON intelligence.event_article_membership (anchor_ref);

COMMENT ON TABLE intelligence.event_article_membership IS
    'TE-first typed evidence membership (event-core). Anonymous related is inadmissible.';

CREATE TABLE IF NOT EXISTS intelligence.tracked_event_storyline_facets (
    id BIGSERIAL PRIMARY KEY,
    tracked_event_id BIGINT NOT NULL
        REFERENCES intelligence.tracked_events (id) ON DELETE CASCADE,
    domain_key TEXT NOT NULL,
    storyline_id BIGINT NOT NULL,
    facet TEXT NOT NULL DEFAULT 'primary',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_te_storyline_facet
        UNIQUE (tracked_event_id, domain_key, storyline_id)
);

CREATE INDEX IF NOT EXISTS idx_te_storyline_facets_storyline
    ON intelligence.tracked_event_storyline_facets (domain_key, storyline_id);

COMMENT ON TABLE intelligence.tracked_event_storyline_facets IS
    'Many domain storyline facets per tracked_event (replaces 1:1 storyline_id for new event-core TEs).';

DO $$
BEGIN
    RAISE NOTICE 'Migration 280: event-core TE anchors + event_article_membership + facets';
END $$;
