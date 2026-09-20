#!/usr/bin/env bash
# Source from install.sh after platform.json exists
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PF="$KIT_ROOT/platform.json"
[[ -f "$PF" ]] || exit 0
EXTRA=$(python3 -c "import json; print(json.load(open('$PF')).get('compose_extra',''))" 2>/dev/null || true)
if [[ -n "$EXTRA" && -f "$KIT_ROOT/$EXTRA" ]]; then
  export COMPOSE_FILES="${COMPOSE_FILES:- -f compose.yaml} -f $EXTRA"
fi
