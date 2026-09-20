#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"
"$KIT_ROOT/scripts/backup_kit.sh"
docker compose pull
docker compose build api intake-web
docker compose up -d
echo "Upgrade complete"
