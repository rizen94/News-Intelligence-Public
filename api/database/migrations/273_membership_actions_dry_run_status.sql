-- Migration 273: dry_run status for membership actions (audit without queue_depth)
-- Dry-run must not inflate status='pending' (Monitor queue_depth / LLM mid-band).

ALTER TABLE intelligence.storyline_membership_actions
    DROP CONSTRAINT IF EXISTS storyline_membership_actions_status_check;

ALTER TABLE intelligence.storyline_membership_actions
    ADD CONSTRAINT storyline_membership_actions_status_check
    CHECK (status IN ('pending', 'applied', 'rejected', 'skipped', 'dry_run'));

-- Existing dry-run proposals were incorrectly stored as pending.
UPDATE intelligence.storyline_membership_actions
SET status = 'dry_run',
    resolved_at = COALESCE(resolved_at, NOW())
WHERE status = 'pending'
  AND rationale ILIKE '%[dry_run]%';

CREATE INDEX IF NOT EXISTS idx_storyline_membership_actions_dry_run
    ON intelligence.storyline_membership_actions (domain_key, created_at DESC)
    WHERE status = 'dry_run';

COMMENT ON TABLE intelligence.storyline_membership_actions IS
    'Queue/audit for storyline membership review. status=pending is human/LLM actionable; dry_run is observe-only progress.';
