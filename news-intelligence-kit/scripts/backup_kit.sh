#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"
STAMP=$(date +%Y%m%d_%H%M%S)
OUT="$KIT_ROOT/data/backups/kit_${STAMP}"
mkdir -p "$OUT"

docker compose exec -T postgres pg_dump -U "${DB_USER:-newsapp}" "${DB_NAME:-news_intel}" > "$OUT/news_intel.sql"
tar -czf "$OUT/vault.tar.gz" -C data vault 2>/dev/null || true
cp .env "$OUT/.env" 2>/dev/null || true
cp -r config/domains "$OUT/domains" 2>/dev/null || true
echo "Backup: $OUT"
