#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$KIT_ROOT/data/support_bundle_$(date +%Y%m%d_%H%M%S).tar.gz"
TMP=$(mktemp -d)
docker compose ps > "$TMP/compose_ps.txt" 2>&1
docker compose logs --tail=200 api > "$TMP/api.log" 2>&1
curl -s "http://localhost:8080/api/setup/status" > "$TMP/setup_status.json" 2>&1 || true
curl -s "http://localhost:8080/api/system_monitoring/kit_status" > "$TMP/kit_status.json" 2>&1 || true
df -h > "$TMP/df.txt"
tar -czf "$OUT" -C "$TMP" .
rm -rf "$TMP"
echo "Support bundle: $OUT (no secrets included)"
