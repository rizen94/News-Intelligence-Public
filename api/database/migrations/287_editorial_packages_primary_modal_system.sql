-- Migration 287: allow modal='system' on editorial package writers/decisions (v11 seed).
-- Idempotent.

ALTER TABLE intelligence.editorial_packages
  DROP CONSTRAINT IF EXISTS editorial_packages_primary_modal_check;

ALTER TABLE intelligence.editorial_packages
  ADD CONSTRAINT editorial_packages_primary_modal_check
  CHECK (
    primary_modal IS NULL
    OR primary_modal IN (
      'intake', 'research', 'narrative', 'reduction', 'editor', 'system'
    )
  );

ALTER TABLE intelligence.editorial_package_members
  DROP CONSTRAINT IF EXISTS editorial_package_members_added_by_modal_check;

ALTER TABLE intelligence.editorial_package_members
  ADD CONSTRAINT editorial_package_members_added_by_modal_check
  CHECK (
    added_by_modal IS NULL
    OR added_by_modal IN (
      'intake', 'research', 'narrative', 'reduction', 'editor', 'system'
    )
  );

ALTER TABLE intelligence.editorial_package_decisions
  DROP CONSTRAINT IF EXISTS editorial_package_decisions_modal_check;

ALTER TABLE intelligence.editorial_package_decisions
  ADD CONSTRAINT editorial_package_decisions_modal_check
  CHECK (
    modal IS NULL
    OR modal IN (
      'intake', 'research', 'narrative', 'reduction', 'editor', 'system'
    )
  );
