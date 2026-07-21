-- Migration 274: per-storyline membership review state (review-once + change requeue)

CREATE TABLE IF NOT EXISTS intelligence.storyline_membership_review_state (
    domain_key TEXT NOT NULL,
    storyline_id BIGINT NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    membership_fingerprint TEXT NOT NULL,
    article_count INT,
    link_count INT,
    PRIMARY KEY (domain_key, storyline_id)
);

CREATE INDEX IF NOT EXISTS idx_storyline_membership_review_state_reviewed
    ON intelligence.storyline_membership_review_state (reviewed_at DESC);

COMMENT ON TABLE intelligence.storyline_membership_review_state IS
    'Last membership-review pass per storyline. Re-queue only when membership_fingerprint changes.';

-- Partial unique-ish helper for pending proposal dedupe lookups
CREATE INDEX IF NOT EXISTS idx_storyline_membership_actions_pending_dedupe
    ON intelligence.storyline_membership_actions (
        domain_key, storyline_id, action, article_id, entity_name, tracked_event_id
    )
    WHERE status = 'pending';
