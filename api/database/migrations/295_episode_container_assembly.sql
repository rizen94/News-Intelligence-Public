-- Migration 295: Event → Episode → Container assembly schema
-- Episodes = {domain}.storylines with fixed anchor_signature
-- Membership SSOT = intelligence.event_episode_links
-- Containers = tracked_events.container_kind + demoted story_kind=container_index
-- Forward-only; does not rewrite existing storyline_articles bags.

-- Tracked events as containers
ALTER TABLE intelligence.tracked_events
    ADD COLUMN IF NOT EXISTS container_kind TEXT;

COMMENT ON COLUMN intelligence.tracked_events.container_kind IS
    'Container index kind: hub_facet | demoted_mega | tracked_index | NULL (legacy follow object). Never owns articles.';

-- Anchor class catalog (identity | supporting | hub)
CREATE TABLE IF NOT EXISTS intelligence.entity_anchor_class (
    id BIGSERIAL PRIMARY KEY,
    domain_key TEXT,
    canonical_entity_id INTEGER,
    entity_name TEXT NOT NULL,
    anchor_class TEXT NOT NULL,
    document_frequency INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'config',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT entity_anchor_class_check CHECK (
        anchor_class IN ('identity', 'supporting', 'hub')
    ),
    CONSTRAINT uq_entity_anchor_class_name
        UNIQUE (domain_key, entity_name)
);

CREATE INDEX IF NOT EXISTS idx_entity_anchor_class_cid
    ON intelligence.entity_anchor_class (canonical_entity_id)
    WHERE canonical_entity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_entity_anchor_class_class
    ON intelligence.entity_anchor_class (anchor_class);

COMMENT ON TABLE intelligence.entity_anchor_class IS
    'Episode/container anchor taxonomy. Hubs never admit episode membership.';

-- Event ↔ episode typed links (membership SSOT)
CREATE TABLE IF NOT EXISTS intelligence.event_episode_links (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL
        REFERENCES public.chronological_events (id) ON DELETE CASCADE,
    domain_key TEXT NOT NULL,
    episode_id BIGINT NOT NULL,
    link_type TEXT NOT NULL,
    matched_anchors JSONB NOT NULL DEFAULT '[]'::jsonb,
    inference_stage TEXT NOT NULL DEFAULT 'candidate',
    blend_rank DOUBLE PRECISION,
    added_by TEXT NOT NULL DEFAULT 'episode_attach_gate',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT event_episode_link_type_check CHECK (
        link_type IN ('founding', 'continuation', 'development')
    ),
    CONSTRAINT event_episode_inference_stage_check CHECK (
        inference_stage IN (
            'hypothesized', 'candidate', 'established', 'quarantined'
        )
    ),
    CONSTRAINT uq_event_episode_link
        UNIQUE (event_id, domain_key, episode_id)
);

CREATE INDEX IF NOT EXISTS idx_event_episode_links_episode
    ON intelligence.event_episode_links (domain_key, episode_id);

CREATE INDEX IF NOT EXISTS idx_event_episode_links_event
    ON intelligence.event_episode_links (event_id);

CREATE INDEX IF NOT EXISTS idx_event_episode_links_stage
    ON intelligence.event_episode_links (inference_stage)
    WHERE inference_stage <> 'quarantined';

COMMENT ON TABLE intelligence.event_episode_links IS
    'Event→episode membership SSOT. Articles reach episodes only via their events.';

-- Per-domain episode columns on storylines
DO $$
DECLARE
  sch TEXT;
BEGIN
  FOR sch IN
    SELECT DISTINCT table_schema
    FROM information_schema.tables
    WHERE table_name = 'storylines'
      AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public')
  LOOP
    BEGIN
      EXECUTE format(
        'ALTER TABLE %I.storylines
           ADD COLUMN IF NOT EXISTS episode_state TEXT NOT NULL DEFAULT ''forming''',
        sch
      );
      EXECUTE format(
        'ALTER TABLE %I.storylines
           ADD COLUMN IF NOT EXISTS anchor_signature JSONB NOT NULL DEFAULT ''{"identity":[],"supporting":[]}''::jsonb',
        sch
      );
      EXECUTE format(
        'ALTER TABLE %I.storylines
           ADD COLUMN IF NOT EXISTS signature_locked_at TIMESTAMPTZ',
        sch
      );
      EXECUTE format(
        'ALTER TABLE %I.storylines
           ADD COLUMN IF NOT EXISTS story_kind TEXT',
        sch
      );
      EXECUTE format(
        'COMMENT ON COLUMN %I.storylines.story_kind IS
           ''Episode shape or container_index for demoted megas (overrides YAML kind when set)''',
        sch
      );
      BEGIN
        EXECUTE format(
          'ALTER TABLE %I.storylines
             DROP CONSTRAINT IF EXISTS storylines_episode_state_check',
          sch
        );
        EXECUTE format(
          'ALTER TABLE %I.storylines
             ADD CONSTRAINT storylines_episode_state_check
             CHECK (episode_state IN (
               ''forming'', ''active'', ''cooling'', ''dormant'', ''concluded''
             ))',
          sch
        );
      EXCEPTION
        WHEN OTHERS THEN
          RAISE NOTICE '295: episode_state check skip % — %', sch, SQLERRM;
      END;
      EXECUTE format(
        'COMMENT ON COLUMN %I.storylines.episode_state IS
           ''Episode lifecycle: forming|active|cooling|dormant|concluded''',
        sch
      );
      EXECUTE format(
        'COMMENT ON COLUMN %I.storylines.anchor_signature IS
           ''Fixed episode anchors {identity:[], supporting:[]}; hubs excluded''',
        sch
      );
      EXECUTE format(
        'COMMENT ON COLUMN %I.storylines.signature_locked_at IS
           ''When anchor_signature was locked at founding / co-anchor growth''',
        sch
      );
    EXCEPTION
      WHEN OTHERS THEN
        RAISE NOTICE '295_episode_container: skip schema % — %', sch, SQLERRM;
    END;
  END LOOP;
END $$;

DO $$
BEGIN
    RAISE NOTICE 'Migration 295: episode_state + anchor_signature + event_episode_links + entity_anchor_class + container_kind';
END $$;
