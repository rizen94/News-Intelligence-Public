#!/usr/bin/env bash
# Build distributable zip from dev tree (run from News Intelligence repo root)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KIT="$ROOT/news-intelligence-kit"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

rsync -a "$KIT/" "$STAGE/news-intelligence-kit/" \
  --exclude data/postgres --exclude data/ollama --exclude '.env'

# Bundle API source required for Docker build (context: parent repo)
mkdir -p "$STAGE/news-intelligence-kit/vendor"
rsync -a "$ROOT/api/" "$STAGE/news-intelligence-kit/vendor/api/" \
  --exclude __pycache__ --exclude '.pytest_cache'

# Optional: pre-build web in parent before export
if [[ -d "$ROOT/web/dist" ]]; then
  mkdir -p "$STAGE/news-intelligence-kit/web/dist"
  rsync -a "$ROOT/web/dist/" "$STAGE/news-intelligence-kit/web/dist/"
fi

(cd "$STAGE" && zip -r "$ROOT/news-intelligence-kit.zip" news-intelligence-kit)
echo "Created $ROOT/news-intelligence-kit.zip"
