#!/usr/bin/env bash
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Open WebUI tools mounted at: $KIT_ROOT/open-webui/tools/"
echo "System prompt: $KIT_ROOT/open-webui/SYSTEM_PROMPT.md"
echo ""
echo "Configure in Open WebUI Admin → Settings → External Tools, or import ni_kit_tools.json."
echo "API base for tools (inside compose): http://api:8000"
ls -la "$KIT_ROOT/open-webui/tools/" 2>/dev/null || true
if [[ -f "$KIT_ROOT/open-webui/SYSTEM_PROMPT.md" ]]; then
  echo ""
  echo "--- System prompt preview ---"
  head -8 "$KIT_ROOT/open-webui/SYSTEM_PROMPT.md"
fi
