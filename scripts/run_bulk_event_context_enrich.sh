#!/usr/bin/env bash
# Event tracking bulk, then context_sync, then content_enrichment (sequential).
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
LOG="${BULK_CATCHUP_LOG:-/tmp/bulk_catchup.log}"
PROGRESS="$ROOT/data/bulk_catchup_progress.json"
LOOPS="${BULK_LOOPS:-50}"
EVENT_LIMIT="${BULK_EVENT_LIMIT:-300}"
CTX_LIMIT="${BULK_CONTEXT_SYNC_LIMIT:-500}"
ENRICH_BATCH="${BULK_ENRICH_BATCH:-120}"

cd "$ROOT"
mkdir -p "$ROOT/data"
# shellcheck source=/dev/null
source "$ROOT/.env" 2>/dev/null || true
# shellcheck source=/dev/null
source "$ROOT/scripts/catchup_env.sh"

"$ROOT/scripts/pause_for_bulk_catchup.sh" 2>&1 | tail -3

PYTHONPATH=api .venv/bin/python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
import importlib.util

root = Path("$ROOT")
from dotenv import load_dotenv
load_dotenv(root / ".env", override=False)
api = root / "api"
spec = importlib.util.spec_from_file_location("_bm", api / "services" / "backlog_metrics.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
pending = mod.get_all_pending_counts()
phases = ("event_tracking", "context_sync", "content_enrichment")
payload = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "phases": {
        p: {"initial_pending": int(pending.get(p) or 0), "status": "pending"}
        for p in phases
    },
    "current_phase": phases[0],
}
out = root / "data" / "bulk_catchup_progress.json"
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"Progress baseline: {out}")
for p in phases:
    print(f"  {p}: {payload['phases'][p]['initial_pending']:,} pending")
PY

run_phase() {
  local phase="$1"
  shift
  local extra=("$@")
  PYTHONPATH=api .venv/bin/python3 - <<PY
import json
from pathlib import Path
p = Path("$PROGRESS")
d = json.loads(p.read_text())
d["current_phase"] = "$phase"
d["phases"]["$phase"]["status"] = "running"
p.write_text(json.dumps(d, indent=2), encoding="utf-8")
PY
  echo "=== bulk phase: $phase ===" | tee -a "$LOG"
  PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup.py \
    --force --phase "$phase" --loops "$LOOPS" "${extra[@]}"
  PYTHONPATH=api .venv/bin/python3 - <<PY
import json
from pathlib import Path
import importlib.util
root = Path("$ROOT")
from dotenv import load_dotenv
load_dotenv(root / ".env", override=False)
spec = importlib.util.spec_from_file_location("_bm", root / "api/services/backlog_metrics.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
pending = int(mod.get_all_pending_counts().get("$phase") or 0)
p = Path("$PROGRESS")
d = json.loads(p.read_text())
d["phases"]["$phase"]["status"] = "done"
d["phases"]["$phase"]["pending_after"] = pending
p.write_text(json.dumps(d, indent=2), encoding="utf-8")
PY
}

if [[ "${1:-}" == "--foreground" ]]; then
  run_phase event_tracking --event-limit "$EVENT_LIMIT"
  run_phase context_sync --context-sync-limit "$CTX_LIMIT"
  run_phase content_enrichment --enrich-batch "$ENRICH_BATCH"
  echo "All phases complete. Progress: $PROGRESS"
  exit 0
fi

nohup env ROOT="$ROOT" PROGRESS="$PROGRESS" LOOPS="$LOOPS" \
  EVENT_LIMIT="$EVENT_LIMIT" CTX_LIMIT="$CTX_LIMIT" ENRICH_BATCH="$ENRICH_BATCH" \
  "$ROOT/scripts/run_bulk_event_context_enrich.sh" --foreground \
  >> "$LOG" 2>&1 &
echo "bulk chain pid=$!"
echo "Log: $LOG"
echo "Watch: $ROOT/scripts/bulk_watch_progress.sh"
