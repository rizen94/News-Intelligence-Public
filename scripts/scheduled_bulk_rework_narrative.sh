#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/pete/Documents/projects/News Intelligence"
LOG="$ROOT/logs/quality_watch/bulk_rework_narrative_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$ROOT/logs/quality_watch"
{
  echo "=== $(date -Is) bulk rework → narrative start ==="
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
  export DB_PORT="${DB_PORT:-6432}"
  cd "$ROOT"
  PYTHONPATH=api "$ROOT/.venv/bin/python" \
    scripts/bulk_rework_packages_to_narrative.py \
    --note "scheduled bulk_rework→narrative 2026-08-16 afternoon fulltext_rebuild" \
    --kick-pass \
    --batch-limit 40
  echo "=== $(date -Is) bulk rework → narrative done ==="
} 2>&1 | tee -a "$LOG"
