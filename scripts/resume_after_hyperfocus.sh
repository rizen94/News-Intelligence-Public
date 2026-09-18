#!/usr/bin/env bash
# Resume routine Widow operations after hyperfocus backlog burndown.
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
STATE="$ROOT/data/hyperfocus_state.json"
CRON_SRC="/etc/cron.d/widow-db-adjacent"
CRON_DISABLED="/etc/cron.d/widow-db-adjacent.disabled"

cd "$ROOT"

if [[ -f "$CRON_DISABLED" ]] && [[ ! -f "$CRON_SRC" ]]; then
  echo "Re-enabling widow-db-adjacent cron"
  sudo mv "$CRON_DISABLED" "$CRON_SRC"
fi

"$ROOT/scripts/resume_after_bulk_catchup.sh"

if [[ -f "$STATE" ]]; then
  API_WAS=$(python3 - <<PY
import json
from pathlib import Path
d = json.loads(Path("$STATE").read_text())
print("true" if d.get("api_was_active") else "false")
PY
)
  if [[ "$API_WAS" == "true" ]]; then
    echo "Starting news-intelligence-api-public (was active before hyperfocus)"
    sudo systemctl start news-intelligence-api-public
  fi
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("""$STATE""")
if p.is_file():
    s = json.loads(p.read_text())
    s["resumed_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(s, indent=2))
PY
fi

echo "Waiting for API readiness..."
if systemctl is-active --quiet news-intelligence-api-public 2>/dev/null; then
  "$ROOT/scripts/systemd_wait_readiness.sh" || true
  curl -sf "http://127.0.0.1:8000/api/health" >/dev/null && echo "API health OK" || echo "API health check failed (may still be starting)"
fi

echo "Resume complete. Monitor pending with: PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup_status.py --watch 60"
