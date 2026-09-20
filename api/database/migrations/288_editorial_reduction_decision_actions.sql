-- Migration 288: editorial package decision actions for Reduction modality (v11).
-- Adds reduction_pass + converged to editorial_package_decisions.action CHECK.
-- Idempotent.

ALTER TABLE intelligence.editorial_package_decisions
  DROP CONSTRAINT IF EXISTS editorial_package_decisions_action_check;

ALTER TABLE intelligence.editorial_package_decisions
  ADD CONSTRAINT editorial_package_decisions_action_check
  CHECK (
    action IN (
      'member_added', 'member_removed', 'member_quarantined',
      'link_added', 'link_removed', 'kind_set', 'ready_for_editor',
      'cleared', 'blocked', 'rework_requested', 'prose_drafted',
      'prose_published', 'citation_bound', 'citation_refused',
      'status_changed', 'package_created',
      'converged', 'reduction_pass'
    )
  );
