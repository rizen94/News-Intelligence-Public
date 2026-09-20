#!/usr/bin/env bash
set -euo pipefail
BACKUP="${1:?Usage: restore_kit.sh /path/to/backup/dir}"
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"

docker compose stop api intake-web open-webui || true
docker compose exec -T postgres psql -U "${DB_USER:-newsapp}" -d "${DB_NAME:-news_intel}" < "$BACKUP/news_intel.sql"
tar -xzf "$BACKUP/vault.tar.gz" -C data 2>/dev/null || true
docker compose up -d
echo "Restore complete from $BACKUP"
