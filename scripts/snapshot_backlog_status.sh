#!/usr/bin/env bash
# Save GET backlog_status + automation/status JSON under .local/backlog_snapshots/ (gitignored),
# then print one timeline table across the current snapshot and up to 3 prior snapshots
# (same metrics, oldest → newest, with Δ oldest→now).
# From repo root you can run: ./snapshot_backlog_status
# Optional: BACKLOG_STATUS_URL, AUTOMATION_STATUS_URL (defaults localhost:8000).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${ROOT}/.local/backlog_snapshots"
mkdir -p "$OUT_DIR"
TS="$(date -u +%Y%m%d_%H%M%S)"

MAX_RETRIES=3
RETRY_DELAY=10

# fetch_with_retry URL OUTFILE MAX_TIME
#   Retries up to MAX_RETRIES times if curl fails or the JSON response has "success": false.
#   Returns 0 on success, 1 if all retries exhausted.
fetch_with_retry() {
  local url="$1" outfile="$2" max_time="$3"
  local attempt=0
  while (( attempt < MAX_RETRIES )); do
    attempt=$((attempt + 1))
    if curl -sS -m "$max_time" "$url" -o "$outfile" 2>/dev/null; then
      if python3 -c "import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if d.get('success',True) else 1)" "$outfile" 2>/dev/null; then
        return 0
      fi
      local msg
      msg=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('message','unknown'))" "$outfile" 2>/dev/null || echo "unknown")
      if (( attempt < MAX_RETRIES )); then
        echo "  ⟳ Attempt ${attempt}/${MAX_RETRIES} got success=false (${msg}), retrying in ${RETRY_DELAY}s..." >&2
        sleep "$RETRY_DELAY"
      else
        echo "  ✗ Attempt ${attempt}/${MAX_RETRIES} got success=false (${msg})" >&2
      fi
    else
      if (( attempt < MAX_RETRIES )); then
        echo "  ⟳ Attempt ${attempt}/${MAX_RETRIES} curl failed, retrying in ${RETRY_DELAY}s..." >&2
        sleep "$RETRY_DELAY"
      else
        echo "  ✗ Attempt ${attempt}/${MAX_RETRIES} curl failed" >&2
      fi
    fi
  done
  return 1
}

URL="${BACKLOG_STATUS_URL:-http://127.0.0.1:8000/api/system_monitoring/backlog_status}"
OUT="${OUT_DIR}/backlog_status_${TS}.json"

if fetch_with_retry "$URL" "$OUT" 120; then
  echo "Wrote $OUT"
else
  echo "ERROR: backlog_status failed after ${MAX_RETRIES} attempts (API too busy?). Removing bad snapshot." >&2
  rm -f "$OUT"
  exit 1
fi

AST_URL="${AUTOMATION_STATUS_URL:-http://127.0.0.1:8000/api/system_monitoring/automation/status}"
AOUT="${OUT_DIR}/automation_status_${TS}.json"

if fetch_with_retry "$AST_URL" "$AOUT" 120; then
  echo "Wrote $AOUT"
else
  echo "WARNING: automation/status failed after ${MAX_RETRIES} attempts. Removing bad file." >&2
  rm -f "$AOUT"
  echo "  (backlog_status was saved; automation_status was not)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Current snapshot"
if [[ -f "$AOUT" ]]; then
  echo "  Files:  $(basename "$OUT")  +  $(basename "$AOUT")"
else
  echo "  Files:  $(basename "$OUT")  (automation_status not captured)"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mapfile -t files < <(ls -1 "$OUT_DIR"/backlog_status_*.json 2>/dev/null | sort || true)
n="${#files[@]}"
newer="$OUT"
new_idx=-1
for ((i = 0; i < n; i++)); do
  if [[ "${files[i]}" == "$newer" ]]; then
    new_idx=$i
    break
  fi
done

if [[ "$new_idx" -lt 0 ]]; then
  echo "warning: new file not found in sorted listing; skipping timeline." >&2
  exit 0
fi

if [[ "$new_idx" -eq 0 ]]; then
  echo ""
  echo "No prior backlog_status snapshots — timeline will appear on the next run."
  exit 0
fi

start=$((new_idx >= 3 ? new_idx - 3 : 0))
timeline_args=()
for ((i = start; i <= new_idx; i++)); do
  timeline_args+=("${files[i]}")
done

echo ""
echo "Progress timeline (${#timeline_args[@]} snapshots, oldest → newest):"
echo ""
uv run python "${ROOT}/scripts/compare_backlog_snapshots.py" timeline "${timeline_args[@]}"

echo ""
echo "Pair diff (last two files only):  ./scripts/backlog_burndown.sh diff"
