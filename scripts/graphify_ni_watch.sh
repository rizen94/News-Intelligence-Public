#!/usr/bin/env bash
# Long-running: rebuild graph on corpus changes (dev session). Not for MCP stdio.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORPUS="${GRAPHIFY_CORPUS:-$ROOT/graphify-trial-corpus/pipeline-full}"
GRAPHIFY="${GRAPHIFY_BIN:-$(command -v graphify || true)}"

if [[ -z "$GRAPHIFY" ]]; then
  echo "graphify not found. uv tool install 'graphifyy[mcp]'" >&2
  exit 1
fi

"$ROOT/scripts/graphify_ni_pipeline_slice.sh"
echo "Watching $CORPUS — Ctrl+C to stop. Retry graphify-ni-pipeline MCP after rebuilds." >&2
exec "$GRAPHIFY" watch "$CORPUS" "$@"
