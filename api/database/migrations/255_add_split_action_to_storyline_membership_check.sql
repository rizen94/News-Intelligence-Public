-- Migration to add 'split' action to storyline_membership_actions.check constraint
-- This enables human-in-the-loop validation of storyline splits

-- Check constraint for storyline membership actions
-- Adding 'split' action to the allowed list of actions

ALTER TABLE intelligence.storyline_membership_actions
DROP CONSTRAINT IF EXISTS storyline_membership_actions_action_check;

ALTER TABLE intelligence.storyline_membership_actions
ADD CONSTRAINT storyline_membership_actions_action_check 
CHECK (action = ANY (ARRAY['unlink'::text, 'demote_relevance'::text, 'quarantine_graph'::text, 'demote_entity'::text, 'unlink_tracked_event'::text, 'split'::text]));