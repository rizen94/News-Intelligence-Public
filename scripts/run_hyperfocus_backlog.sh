#!/usr/bin/env bash
# Hyperfocus backlog burndown: quiesce Widow, run major phases sequentially, optional resume.
#
# Usage:
#   ./scripts/run_hyperfocus_backlog.sh quiesce
#   ./scripts/run_hyperfocus_backlog.sh run-all          # blocking; all P0/P1 waves
#   ./scripts/run_hyperfocus_backlog.sh run-dossier-story    # entity_dossier_compile then story_enhancement
#   ./scripts/run_hyperfocus_backlog.sh run-dossier-story-bg # same, background
#   ./scripts/run_hyperfocus_backlog.sh wave event_extraction
#   ./scripts/run_hyperfocus_backlog.sh upstream         # if upstream > floor
#   ./scripts/run_hyperfocus_backlog.sh status
#   ./scripts/run_hyperfocus_backlog.sh finish-all-gpu      # drain all major + bulk phases (PopOS GPU)
#   ./scripts/run_hyperfocus_backlog.sh finish-all-gpu-bg   # same, background
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
STATE="$ROOT/data/hyperfocus_state.json"
FLOOR="${HYPERFOCUS_FLOOR:-200}"
LOOPS="${HYPERFOCUS_LOOPS:-300}"
LOG_DIR="$ROOT/logs"

cd "$ROOT"
mkdir -p "$LOG_DIR" "$ROOT/data"

_load_db_password() {
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  if [[ -f "$ROOT/.db_password_widow" ]]; then
    export DB_PASSWORD
    DB_PASSWORD="$(cat "$ROOT/.db_password_widow")"
  fi
  set +a
  # shellcheck source=/dev/null
  source "$ROOT/scripts/catchup_env.sh"
}

_export_hyperfocus_env() {
  export MAJOR_CATCHUP_LOOPS="$LOOPS"
  export MAJOR_CATCHUP_FLOOR="$FLOOR"
}

_start_dossier_gpu_companions() {
  local with_profile="${1:-0}"
  local narrative_log="$LOG_DIR/hyperfocus_dossier_narrative.log"
  echo "Starting PopOS GPU dossier narrative backfill (parallel)"
  cmd_wave entity_dossier_narrative >>"$narrative_log" 2>&1 &
  echo $! >"$LOG_DIR/hyperfocus_gpu_narrative.pid"
  if [[ "$with_profile" == "1" ]]; then
    local profile_log="$LOG_DIR/hyperfocus_entity_profile_build.log"
    echo "Starting PopOS GPU entity_profile_build (parallel)"
    cmd_wave entity_profile_build >>"$profile_log" 2>&1 &
    echo $! >"$LOG_DIR/hyperfocus_gpu_profile.pid"
  fi
}

_wait_dossier_gpu_companions() {
  local pid
  echo "Waiting for PopOS GPU companions to finish..."
  for f in hyperfocus_gpu_narrative.pid hyperfocus_gpu_profile.pid; do
    if [[ -f "$LOG_DIR/$f" ]]; then
      pid="$(cat "$LOG_DIR/$f" 2>/dev/null || true)"
      if [[ -n "${pid:-}" ]]; then
        wait "$pid" 2>/dev/null || true
      fi
    fi
  done
}

_pending_for() {
  local phase="$1"
  _load_db_password
  .venv/bin/python3 - <<PY
from services.backlog_metrics import invalidate_backlog_metrics_cache, get_all_pending_counts
invalidate_backlog_metrics_cache()
print(int(get_all_pending_counts().get("$phase") or 0))
PY
}

_snapshot_wave() {
  local wave="$1" label="$2"
  local pending
  pending="$(_pending_for "$wave")"
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
waves = s.setdefault("waves", {})
waves["$wave"] = waves.get("$wave", {})
waves["$wave"]["$label"] = {"at": datetime.now(timezone.utc).isoformat(), "pending": int("$pending")}
p.write_text(json.dumps(s, indent=2))
PY
  echo "  $wave $label pending=$pending"
}

_run_major_wave() {
  local phase="$1"
  shift
  local log="$LOG_DIR/hyperfocus_${phase}.log"
  echo "=== Wave $phase ($(date -u -Iseconds)) log=$log ==="
  _snapshot_wave "$phase" "before"
  _load_db_password
  _export_hyperfocus_env
  # shellcheck disable=SC2068
  .venv/bin/python3 api/scripts/run_major_backlog_catchup.py \
    --force --use-popos-gpu \
    --phases "$phase" \
    --floor "$FLOOR" --loops "$LOOPS" \
    "$@" \
    2>&1 | tee -a "$log"
  local rc=${PIPESTATUS[0]}
  _snapshot_wave "$phase" "after"
  return "$rc"
}

cmd_quiesce() {
  "$ROOT/scripts/quiesce_for_hyperfocus.sh"
}

cmd_wave() {
  local phase="${1:?phase name required}"
  case "$phase" in
    event_extraction)
      _run_major_wave event_extraction --dual-lane
      ;;
    story_enhancement)
      _run_major_wave story_enhancement --no-dual-lane --story-facts-only
      ;;
    entity_profile_build)
      _run_major_wave entity_profile_build --no-dual-lane
      ;;
    entity_dossier_compile)
      _run_major_wave entity_dossier_compile --no-dual-lane
      ;;
    entity_dossier_narrative)
      _run_major_wave entity_dossier_narrative --no-dual-lane --floor 0
      ;;
    *)
      echo "Unknown wave: $phase" >&2
      exit 1
      ;;
  esac
}

cmd_upstream() {
  _load_db_password
  _export_hyperfocus_env
  local need=false
  for phase in entity_extraction claim_extraction context_sync; do
    p="$(_pending_for "$phase")"
    echo "  $phase: $p"
    if [[ "$p" -gt "$FLOOR" ]]; then
      need=true
    fi
  done
  if [[ "$need" != true ]]; then
    echo "Upstream phases at or below floor $FLOOR — skipping bulk_catchup"
    return 0
  fi
  local log="$LOG_DIR/hyperfocus_upstream.log"
  echo "=== Upstream bulk_catchup log=$log ==="
  .venv/bin/python3 api/scripts/bulk_catchup.py \
    --force --use-popos-gpu --dual-lane --parallel 6 \
    --floor "$FLOOR" --loops 100 \
    2>&1 | tee -a "$log"
}

cmd_run_all() {
  cmd_quiesce
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
s["run_all_started_at"] = datetime.now(timezone.utc).isoformat()
s["floor"] = int("$FLOOR")
s["loops"] = int("$LOOPS")
p.write_text(json.dumps(s, indent=2))
PY
  cmd_wave event_extraction
  cmd_wave story_enhancement
  cmd_wave entity_profile_build
  _start_dossier_gpu_companions 0
  cmd_wave entity_dossier_compile
  _wait_dossier_gpu_companions
  cmd_upstream
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
s["run_all_finished_at"] = datetime.now(timezone.utc).isoformat()
p.write_text(json.dumps(s, indent=2))
PY
  echo "=== Hyperfocus run-all complete $(date -u -Iseconds) ==="
  echo "Resume routine ops: $ROOT/scripts/resume_after_hyperfocus.sh"
}

cmd_run_dossier_story() {
  cmd_quiesce
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
s["run_dossier_story_started_at"] = datetime.now(timezone.utc).isoformat()
s["floor"] = int("$FLOOR")
s["loops"] = int("$LOOPS")
p.write_text(json.dumps(s, indent=2))
PY
  _start_dossier_gpu_companions 1
  cmd_wave entity_dossier_compile
  _wait_dossier_gpu_companions
  cmd_wave story_enhancement
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
s["run_dossier_story_finished_at"] = datetime.now(timezone.utc).isoformat()
p.write_text(json.dumps(s, indent=2))
PY
  echo "=== Dossier + story catch-up complete $(date -u -Iseconds) ==="
  echo "Resume routine ops: $ROOT/scripts/resume_after_hyperfocus.sh"
}

cmd_run_dossier_narrative_sweep() {
  cmd_quiesce
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
s["run_dossier_narrative_sweep_started_at"] = datetime.now(timezone.utc).isoformat()
s["floor"] = 0
s["loops"] = int("${HYPERFOCUS_NARRATIVE_LOOPS:-800}")
p.write_text(json.dumps(s, indent=2))
PY

  local narrative_loops="${HYPERFOCUS_NARRATIVE_LOOPS:-800}"
  local narrative_parallel="${DOSSIER_NARRATIVE_PARALLEL:-6}"
  local cpu_parallel="${DOSSIER_NARRATIVE_CPU_PARALLEL:-4}"
  export DOSSIER_NARRATIVE_PARALLEL="$narrative_parallel"
  export DOSSIER_NARRATIVE_CPU_PARALLEL="$cpu_parallel"
  export DOSSIER_NARRATIVE_MODEL="${DOSSIER_NARRATIVE_MODEL:-qwen2.5:7b-instruct}"

  echo "=== Narrative-only sweep (PopOS GPU + Widow CPU, floor=0, loops=$narrative_loops) ==="
  echo "GPU workers: $narrative_parallel | CPU workers: $cpu_parallel | Model: ${DOSSIER_NARRATIVE_MODEL}"

  # Launch GPU + CPU narrative workers in parallel
  local gpu_log="$LOG_DIR/hyperfocus_dossier_narrative.log"
  local cpu_log="$LOG_DIR/hyperfocus_dossier_narrative_cpu.log"
  cmd_wave entity_dossier_narrative >>"$gpu_log" 2>&1 &
  local gpu_pid=$!
  echo $gpu_pid >"$LOG_DIR/hyperfocus_gpu_narrative.pid"

  # Start CPU-only narrative workers (same phase, different lane)
  if [[ "$cpu_parallel" -gt 0 ]]; then
    export DOSSIER_CATCHUP_GPU_NARRATIVE="false"
    cmd_wave entity_dossier_narrative >>"$cpu_log" 2>&1 &
    local cpu_pid=$!
    echo $cpu_pid >"$LOG_DIR/hyperfocus_cpu_narrative.pid"
  fi

  echo "Waiting for narrative workers..."
  wait $gpu_pid 2>/dev/null || true
  [[ "$cpu_parallel" -gt 0 ]] && wait $cpu_pid 2>/dev/null || true

  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
s["run_dossier_narrative_sweep_finished_at"] = datetime.now(timezone.utc).isoformat()
p.write_text(json.dumps(s, indent=2))
PY
  echo "=== Narrative sweep complete $(date -u -Iseconds) ==="
  echo "Resume routine ops: $ROOT/scripts/resume_after_hyperfocus.sh"
}

cmd_run_dossier_narrative_sweep_bg() {
  local log="$LOG_DIR/hyperfocus_dossier_narrative_sweep_orchestrator.log"
  nohup "$0" run-dossier-narrative-sweep >>"$log" 2>&1 &
  echo "Dossier narrative sweep pid=$! log=$log"
  echo "Monitor: tail -f $log"
  echo "Status:  $0 status"
}

cmd_run_dossier_story_bg() {
  local log="$LOG_DIR/hyperfocus_dossier_story_orchestrator.log"
  nohup "$0" run-dossier-story >>"$log" 2>&1 &
  echo "Dossier→story catch-up pid=$! log=$log"
  echo "Monitor: tail -f $log"
  echo "Status:  $0 status"
}

cmd_run_all_bg() {
  nohup "$0" run-all >>"$LOG_DIR/hyperfocus_orchestrator.log" 2>&1 &
  echo "Hyperfocus orchestrator pid=$! log=$LOG_DIR/hyperfocus_orchestrator.log"
}

cmd_status() {
  _load_db_password
  echo "=== Hyperfocus status $(date -u -Iseconds) ==="
  [[ -f "$STATE" ]] && cat "$STATE" || echo "(no state file)"
  echo "--- pending (major phases) ---"
  for phase in entity_dossier_compile entity_dossier_narrative story_enhancement entity_profile_build event_extraction; do
    echo "  $phase: $(_pending_for "$phase")"
  done
  echo "--- processes ---"
  pgrep -af "run_hyperfocus_backlog|run_major_backlog_catchup|bulk_catchup" || echo "(none)"
  systemctl is-active news-intelligence-api-public 2>/dev/null || echo "api: inactive"
}

_run_bulk_all() {
  local log="$LOG_DIR/hyperfocus_finish_bulk.log"
  echo "=== bulk_catchup all phases floor=0 ($(date -u -Iseconds)) log=$log ==="
  _load_db_password
  _export_hyperfocus_env
  .venv/bin/python3 api/scripts/bulk_catchup.py \
    --force --use-popos-gpu --dual-lane --parallel 6 \
    --floor 0 --loops "$LOOPS" \
    2>&1 | tee -a "$log"
}

cmd_finish_all_gpu() {
  local saved_floor="$FLOOR"
  local saved_loops="$LOOPS"
  FLOOR=0
  LOOPS="${HYPERFOCUS_FINISH_LOOPS:-1500}"
  export DOSSIER_NARRATIVE_PARALLEL="${DOSSIER_NARRATIVE_PARALLEL:-8}"
  export DOSSIER_NARRATIVE_CPU_PARALLEL="${DOSSIER_NARRATIVE_CPU_PARALLEL:-4}"
  export DOSSIER_NARRATIVE_MODEL="${DOSSIER_NARRATIVE_MODEL:-qwen2.5:7b-instruct}"

  cmd_quiesce
  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
s["finish_all_gpu_started_at"] = datetime.now(timezone.utc).isoformat()
s["floor"] = 0
s["loops"] = int("$LOOPS")
p.write_text(json.dumps(s, indent=2))
PY

  echo "=== Finish-all backlog (PopOS GPU, floor=0, loops=$LOOPS) ==="
  _run_bulk_all
  cmd_wave event_extraction
  cmd_wave entity_profile_build
  cmd_wave entity_dossier_compile

  echo "=== Dedicated narrative sweep (GPU + CPU, no competing work) ==="
  _start_dossier_gpu_companions 0  # only narrative, no profile build
  _wait_dossier_gpu_companions

  cmd_wave story_enhancement

  python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("$STATE")
s = json.loads(p.read_text()) if p.is_file() else {}
s["finish_all_gpu_finished_at"] = datetime.now(timezone.utc).isoformat()
p.write_text(json.dumps(s, indent=2))
PY
  FLOOR="$saved_floor"
  LOOPS="$saved_loops"
  echo "=== Finish-all GPU complete $(date -u -Iseconds) ==="
  echo "Resume routine ops: $ROOT/scripts/resume_after_hyperfocus.sh"
}

cmd_finish_all_gpu_bg() {
  local log="$LOG_DIR/hyperfocus_finish_all_gpu_orchestrator.log"
  nohup "$0" finish-all-gpu >>"$log" 2>&1 &
  echo "Finish-all GPU backlog pid=$! log=$log"
  echo "Monitor: tail -f $log"
  echo "Status:  $0 status"
}

cmd_resume() {
  "$ROOT/scripts/resume_after_hyperfocus.sh"
}

main() {
  local cmd="${1:-status}"
  shift || true
  case "$cmd" in
    quiesce) cmd_quiesce ;;
    wave) cmd_wave "$@" ;;
    run-all) cmd_run_all ;;
    run-all-bg) cmd_run_all_bg ;;
    run-dossier-story) cmd_run_dossier_story ;;
    run-dossier-story-bg) cmd_run_dossier_story_bg ;;
    upstream) cmd_upstream ;;
    status) cmd_status ;;
    finish-all-gpu) cmd_finish_all_gpu ;;
    finish-all-gpu-bg) cmd_finish_all_gpu_bg ;;
    run-dossier-narrative-sweep) cmd_run_dossier_narrative_sweep ;;
    run-dossier-narrative-sweep-bg) cmd_run_dossier_narrative_sweep_bg ;;
    resume) cmd_resume ;;
    *)
      echo "Usage: $0 {quiesce|wave|run-all|run-all-bg|run-dossier-story|run-dossier-story-bg|run-dossier-narrative-sweep|run-dossier-narrative-sweep-bg|finish-all-gpu|finish-all-gpu-bg|upstream|status|resume}" >&2
      exit 1
      ;;
  esac
}

main "$@"
