-- Grow medicine / AI storyline link capacity: promote suggest_only → auto_approve
-- so automation can clear stubborn unlinked residuals (not just suggest).

UPDATE medicine.storylines
SET automation_mode = 'auto_approve',
    automation_enabled = true,
    updated_at = NOW()
WHERE COALESCE(automation_mode, '') = 'suggest_only'
  AND automation_enabled = true;

UPDATE artificial_intelligence.storylines
SET automation_mode = 'auto_approve',
    automation_enabled = true,
    updated_at = NOW()
WHERE COALESCE(automation_mode, '') = 'suggest_only'
  AND automation_enabled = true;
