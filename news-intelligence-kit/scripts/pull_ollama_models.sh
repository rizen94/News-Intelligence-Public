#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"
source "$KIT_ROOT/.env" 2>/dev/null || true

TIER="${KIT_HARDWARE_TIER:-standard}"
MODELS=(llama3.1:8b nomic-embed-text)
case "$TIER" in
  minimal) ;;
  standard) MODELS+=(phi3.5:latest) ;;
  performance) MODELS+=(phi3.5:latest mistral-nemo:12b) ;;
esac

HOST="${OLLAMA_HOST:-http://localhost:11434}"
for m in "${MODELS[@]}"; do
  echo "Pulling $m ..."
  docker compose exec -T ollama ollama pull "$m" || curl -s "$HOST/api/pull" -d "{\"name\":\"$m\"}" || true
done
