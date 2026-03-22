#!/bin/bash
# Phase 3: Database migration from NAS to Widow
# Requires: SSH tunnel to NAS (localhost:5433), Docker, ssh widow, .db_password_widow
# Run from PRIMARY machine.

set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "Phase 3: Dumping from NAS (localhost:5433) and restoring to Widow..."

# Dump via Docker (primary has tunnel)
mkdir -p /tmp/news_migration
docker run --rm --network host -e PGPASSWORD=newsapp_password \
  -v /tmp/news_migration:/out postgres:16 \
  pg_dump -h 127.0.0.1 -p 5433 -U newsapp -d news_intelligence \
  -F c -Z 5 -f /out/nas_dump.pgdump

# Copy to Widow
scp /tmp/news_migration/nas_dump.pgdump widow:/tmp/nas_dump.pgdump

# Restore on Widow
WIDOW_PASS=$(cat .db_password_widow 2>/dev/null)
ssh widow "PGPASSWORD='$WIDOW_PASS' pg_restore -h 127.0.0.1 -U newsapp -d news_intel -v --no-owner --no-privileges /tmp/nas_dump.pgdump" || true

# Cleanup
ssh widow "rm -f /tmp/nas_dump.pgdump"
rm -rf /tmp/news_migration

echo "✅ Phase 3 complete. Validate with: psql -h 192.168.93.101 -U newsapp -d news_intel -c 'SELECT COUNT(*) FROM information_schema.tables;'"
