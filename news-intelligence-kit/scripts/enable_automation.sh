#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"
sed -i 's/^NEWS_INTEL_DISABLE_AUTOMATION=.*/NEWS_INTEL_DISABLE_AUTOMATION=false/' .env || echo 'NEWS_INTEL_DISABLE_AUTOMATION=false' >> .env
docker compose restart api
echo "Automation enabled — API restarted"
