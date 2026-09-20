-- Migration 286: Unique partial index for legacy package seed idempotency (v11).
-- Local news_intel_dev first; do NOT apply on Widow until v11 cutover.
-- Idempotent.

CREATE SCHEMA IF NOT EXISTS intelligence;

-- One package per legacy_seed key (e.g. storyline:politics:42).
CREATE UNIQUE INDEX IF NOT EXISTS uq_editorial_packages_legacy_seed
  ON intelligence.editorial_packages ((metadata->>'legacy_seed'))
  WHERE metadata ? 'legacy_seed'
    AND COALESCE(metadata->>'legacy_seed', '') <> '';
