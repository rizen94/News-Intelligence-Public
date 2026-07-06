#!/usr/bin/env bash
# LAST RESORT: wipe kit data volumes (Postgres, Ollama models, vault). Keeps config/.
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"

echo "WARNING: This deletes data/postgres, data/ollama, and vault contents."
read -r -p "Type RESET to continue: " confirm
[[ "$confirm" == "RESET" ]] || { echo "Aborted."; exit 1; }

docker compose down
rm -rf data/postgres data/ollama
find data/vault -mindepth 1 ! -name README.md -exec rm -rf {} + 2>/dev/null || true

docker compose up -d
echo "Data reset. Open http://localhost:${INTAKE_WEB_PORT:-8080}/setup/"
