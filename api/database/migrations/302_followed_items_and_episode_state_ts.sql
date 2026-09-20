-- Migration 302: Follow registry + episode_state_changed_at for pulse lifecycle signals

CREATE TABLE IF NOT EXISTS intelligence.followed_items (
    id BIGSERIAL PRIMARY KEY,
    object_kind TEXT NOT NULL,
    domain_key TEXT,
    object_id BIGINT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'quiet',
    user_key TEXT NOT NULL DEFAULT 'operator',
    notify_on TEXT NOT NULL DEFAULT 'any_movement',
    status TEXT NOT NULL DEFAULT 'active',
    last_surfaced_at TIMESTAMPTZ,
    last_read_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT followed_items_object_kind_check CHECK (
        object_kind IN ('episode', 'container', 'package')
    ),
    CONSTRAINT followed_items_tier_check CHECK (
        tier IN ('quiet', 'living')
    ),
    CONSTRAINT followed_items_notify_on_check CHECK (
        notify_on IN ('any_movement', 'state_change', 'republish')
    ),
    CONSTRAINT followed_items_status_check CHECK (
        status IN ('active', 'paused', 'archived')
    ),
    CONSTRAINT uq_followed_items_object UNIQUE (
        user_key, object_kind, domain_key, object_id
    )
);

CREATE INDEX IF NOT EXISTS idx_followed_items_user_status_surfaced
    ON intelligence.followed_items (user_key, status, last_surfaced_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_followed_items_object_lookup
    ON intelligence.followed_items (object_kind, domain_key, object_id);

CREATE INDEX IF NOT EXISTS idx_followed_items_living_package
    ON intelligence.followed_items ((metadata->>'package_id'))
    WHERE tier = 'living' AND status = 'active';

COMMENT ON TABLE intelligence.followed_items IS
    'Operator follow registry: quiet track (surface movement) vs living (published republish loop).';

-- episode_state_changed_at on per-domain storylines (pulse lifecycle transitions)
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
           ADD COLUMN IF NOT EXISTS episode_state_changed_at TIMESTAMPTZ',
        sch
      );
      EXECUTE format(
        'COMMENT ON COLUMN %I.storylines.episode_state_changed_at IS
           ''Last episode_state transition (pulse lifecycle signal)''',
        sch
      );
    EXCEPTION
      WHEN OTHERS THEN
        RAISE NOTICE '300: episode_state_changed_at skip % — %', sch, SQLERRM;
    END;
  END LOOP;
END $$;

DO $$
BEGIN
    RAISE NOTICE 'Migration 302: followed_items + episode_state_changed_at';
END $$;
