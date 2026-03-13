#!/usr/bin/env bash
# Commit context-centric Phase 1–3 and doc/repo hygiene in logical chunks.
# Run from project root: bash scripts/commit_context_centric.sh
# Requires: no uncommitted changes you want to keep split (or run one chunk at a time).

set -e
cd "$(dirname "$0")/.."

echo "=== 1. Migrations and runners ==="
git add \
  api/database/migrations/142_context_centric_foundation.sql \
  api/database/migrations/143_context_centric_entity_claims.sql \
  api/database/migrations/144_v6_events_entity_dossiers.sql \
  api/database/migrations/145_context_entity_mentions.sql \
  api/scripts/run_migration_142_143_144.py \
  api/scripts/run_migration_145.py
git status --short
read -p "Commit 1 (migrations)? [y/N] " r; if [ "$r" = "y" ] || [ "$r" = "Y" ]; then git commit -m "feat(migrations): context-centric 142–145 and runners"; fi

echo "=== 2. Context-centric services ==="
git add \
  api/services/context_processor_service.py \
  api/services/entity_profile_sync_service.py \
  api/services/claim_extraction_service.py \
  api/services/event_tracking_service.py \
  api/services/entity_profile_builder_service.py \
  api/services/pattern_recognition_service.py
git status --short
read -p "Commit 2 (services)? [y/N] " r; if [ "$r" = "y" ] || [ "$r" = "Y" ]; then git commit -m "feat(context-centric): Phase 1–2 services (context, entity profiles, claims, events, pattern recognition)"; fi

echo "=== 3. Config and automation wiring ==="
git add \
  api/config/context_centric.yaml \
  api/config/context_centric_config.py \
  api/services/automation_manager.py \
  api/collectors/rss_collector.py
git status --short
read -p "Commit 3 (config + automation)? [y/N] " r; if [ "$r" = "y" ] || [ "$r" = "Y" ]; then git commit -m "feat(context-centric): config and automation tasks (context_sync, claim_extraction, event_tracking, etc.)"; fi

echo "=== 4. Context-centric API routes ==="
git add \
  api/domains/intelligence_hub/routes/context_centric.py \
  api/domains/intelligence_hub/routes/__init__.py
git status --short
read -p "Commit 4 (API routes)? [y/N] " r; if [ "$r" = "y" ] || [ "$r" = "Y" ]; then git commit -m "feat(api): context-centric read-only API (entity_profiles, contexts, tracked_events, claims, status, quality)"; fi

echo "=== 5. Test for context-centric ==="
git add api/tests/test_context_centric_imports.py
git status --short
read -p "Commit 5 (test)? [y/N] " r; if [ "$r" = "y" ] || [ "$r" = "Y" ]; then git commit -m "test: context-centric import and route registration smoke test"; fi

echo "=== 6. Docs and plan ==="
git add \
  docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md \
  docs/DOCS_INDEX.md \
  docs/REPO_MAINTENANCE.md \
  docs/CLEANUP_PLAN.md \
  docs/PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md \
  docs/CONTROLLER_ARCHITECTURE.md \
  docs/ORCHESTRATOR_ROADMAP_TO_INITIATIVE.md \
  docs/V6_QUALITY_FIRST_TODO.md \
  docs/V6_QUALITY_FIRST_UPGRADE_PLAN.md \
  docs/README.md
git status --short
read -p "Commit 6 (docs)? [y/N] " r; if [ "$r" = "y" ] || [ "$r" = "Y" ]; then git commit -m "docs: context-centric plan, DOCS_INDEX, REPO_MAINTENANCE, cleanup and cross-links"; fi

echo "=== 7. Repo hygiene and archive ==="
git add .gitignore .cursorignore README.md QUICK_START.md scripts/commit_context_centric.sh
git add docs/_archive/ 2>/dev/null || true
# Stage any deleted docs (moved to _archive) if present
for f in docs/REMAINING_DOCUMENTATION_TASKS.md docs/ARCHITECTURAL_STANDARDS.md docs/DEVELOPMENT_METHODOLOGY.md docs/GPU_SETUP.md docs/PHASE5_DEPLOYMENT.md docs/RELEASE_v4.1_WIDOW_MIGRATION.md; do
  git add "$f" 2>/dev/null || true
done
git status --short
read -p "Commit 7 (repo hygiene + archive)? [y/N] " r; if [ "$r" = "y" ] || [ "$r" = "Y" ]; then git commit -m "chore: .gitignore/.cursorignore, README/QUICK_START, doc archive and hygiene"; fi

echo "Done. Remaining changes (if any) left unstaged for you to commit separately."
git status --short
