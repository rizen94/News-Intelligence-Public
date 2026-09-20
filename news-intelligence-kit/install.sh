#!/usr/bin/env bash
# News Intelligence Kit — Linux/WSL installer
set -euo pipefail

KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KIT_ROOT"
FROM_WIN=false
for arg in "$@"; do
  [[ "$arg" == "--from-windows-bootstrap" ]] && FROM_WIN=true
done

if [[ -n "${MSYSTEM:-}" ]] || [[ "$(uname -s)" == MINGW* ]]; then
  echo "Run INSTALL-WINDOWS.bat from File Explorer on Windows."
  exit 1
fi

if [[ "$FROM_WIN" != true ]]; then
  source "$KIT_ROOT/scripts/detect_platform.sh" 2>/dev/null || true
fi
source "$KIT_ROOT/scripts/detect_hardware.sh" 2>/dev/null || true

if [[ ! -f .env ]]; then
  cp .env.template .env
  DB_PASS="$(openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | xxd -p)"
  sed -i "s/change_me_generate_on_install/${DB_PASS}/" .env
fi

# Avoid Ollama host port conflict with system Ollama (default kit uses 11435)
if command -v ss >/dev/null 2>&1 && ss -tln | grep -q ':11434 '; then
  if ! grep -q '^OLLAMA_HOST_PORT=' .env 2>/dev/null; then
    echo "OLLAMA_HOST_PORT=11435" >> .env
    echo "Host Ollama on :11434 detected — kit Ollama will use host port 11435"
  fi
fi
if command -v ss >/dev/null 2>&1 && ss -tln | grep -q ':8080 '; then
  if ! grep -q '^INTAKE_WEB_PORT=' .env 2>/dev/null; then
    echo "INTAKE_WEB_PORT=8081" >> .env
    echo "Host service on :8080 detected — kit intake web will use host port 8081"
  fi
fi

mkdir -p data/postgres data/ollama data/vault data/open-webui
mkdir -p data/vault/{entities,events,threads,hypotheses,domains}

COMPOSE_FILES="-f compose.yaml"
if [[ -f platform.json ]]; then
  # shellcheck disable=SC1091
  source "$KIT_ROOT/scripts/compose_profile_from_platform.sh" || true
fi

echo "Pulling images..."
docker compose $COMPOSE_FILES pull

echo "Building API and web..."
docker compose $COMPOSE_FILES build api intake-web

echo "Starting stack..."
docker compose $COMPOSE_FILES up -d

# Load ports for messages below
# shellcheck disable=SC1091
source "$KIT_ROOT/.env" 2>/dev/null || true

echo "Waiting for API..."
"$KIT_ROOT/scripts/verify_kit.sh" || true

echo "Pulling Ollama models (background-friendly)..."
"$KIT_ROOT/scripts/pull_ollama_models.sh" || true

"$KIT_ROOT/scripts/import_owui_tools.sh" || true

echo ""
echo "Setup UI: http://localhost:${INTAKE_WEB_PORT:-8080}/setup/"
echo "Open WebUI: http://localhost:${OPENWEBUI_PORT:-3001}/"
echo "Run ./scripts/repair.sh if anything failed."
