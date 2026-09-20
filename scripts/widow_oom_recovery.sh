#!/usr/bin/env bash
# Widow NI console recovery after OOM / systemd oom-kill.
#
# Safe defaults for console/IPMI when SSH is down under load:
#   - diagnose (free / uptime / dmesg OOM / unit status)
#   - stop API
#   - backup .env and upsert safer concurrency caps (idempotent)
#   - optionally copy debug instrumentation from the Widow workspace repo
#   - start API and poll health on :8000
#
# Does NOT: git commit/push, deploy remotely, raise concurrency, or touch DB.
#
# Console usage (as root or a sudo-capable user on Widow):
#   sudo bash /path/to/widow_oom_recovery.sh
#   # or from the workspace copy:
#   sudo bash "/home/pete/Documents/projects/News Intelligence/scripts/widow_oom_recovery.sh"
#
# Optional env overrides:
#   NEWS_INTEL_ROOT   production root (default: /opt/news-intelligence)
#   DEV_REPO_ROOT     workspace with instrumentation (default below)
#   SKIP_DEBUG_COPY=1 skip optional file copies
#   HEALTH_URL        health poll URL
#   HEALTH_ATTEMPTS   poll count (default 36)
#   HEALTH_SLEEP_SEC  sleep between polls (default 5)

set -euo pipefail

UNIT="${UNIT:-news-intelligence-api-public.service}"
ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
ENV_FILE="${ROOT}/.env"
DEV_REPO_ROOT="${DEV_REPO_ROOT:-/home/pete/Documents/projects/News Intelligence}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/system_monitoring/health}"
READINESS_URL="${READINESS_URL:-http://127.0.0.1:8000/api/system_monitoring/startup/readiness}"
HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-36}"
HEALTH_SLEEP_SEC="${HEALTH_SLEEP_SEC:-5}"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${ROOT}/backups/oom_recovery_${TS}"

# Safer concurrency (post-OOM). Keep conservative; do not raise here.
SAFE_KEYS=(
  "AUTOMATION_MAX_CONCURRENT_TASKS=2"
  "MAX_CONCURRENT_OLLAMA_TASKS=2"
  "ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE=20"
  "ENTITY_PROFILE_BUILD_LIMIT=40"
)

# Optional debug instrumentation sources → destinations under $ROOT.
# Copied only when the source file exists under DEV_REPO_ROOT.
DEBUG_COPY_PAIRS=(
  "api/main.py|api/main.py"
  "api/services/startup_readiness.py|api/services/startup_readiness.py"
  "scripts/systemd_wait_readiness.sh|scripts/systemd_wait_readiness.sh"
)

_log() { printf '[%s] %s\n' "$(date -Iseconds)" "$*"; }
_warn() { printf '[%s] WARN: %s\n' "$(date -Iseconds)" "$*" >&2; }

_require_rootish() {
  if [[ "${EUID}" -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
    echo "Need root or sudo for systemctl / .env edits." >&2
    exit 1
  fi
}

_run() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

# Idempotent KEY=VALUE upsert in .env (exact key line match).
_set_kv() {
  local key="$1"
  local val="$2"
  local file="$3"
  if grep -qE "^${key}=" "$file" 2>/dev/null; then
    # Preserve file; replace first matching assignment only.
    sed -i -E "s|^${key}=.*|${key}=${val}|" "$file"
  else
    printf '\n%s=%s\n' "$key" "$val" >>"$file"
  fi
}

_diagnose() {
  _log "=== diagnose ==="
  echo "--- uptime ---"
  uptime || true
  echo "--- free -h ---"
  free -h || true
  echo "--- dmesg OOM (tail) ---"
  # Prefer journal/dmesg; never fail the script on permission/empty.
  if command -v dmesg >/dev/null 2>&1; then
    dmesg -T 2>/dev/null | grep -iE 'oom|killed process|out of memory' | tail -n 40 \
      || dmesg 2>/dev/null | grep -iE 'oom|killed process|out of memory' | tail -n 40 \
      || echo "(no OOM lines in dmesg)"
  else
    echo "(dmesg unavailable)"
  fi
  echo "--- systemctl status ${UNIT} ---"
  _run systemctl status "$UNIT" --no-pager -l || true
  echo "--- recent journal (oom / killed) ---"
  _run journalctl -u "$UNIT" -n 80 --no-pager 2>/dev/null \
    | grep -iE 'oom|killed|status=9|Result:' | tail -n 30 \
    || echo "(no matching journal lines)"
}

_stop_api() {
  _log "=== stop ${UNIT} ==="
  _run systemctl stop "$UNIT" || true
  # Brief settle so listeners release :8000
  sleep 2
  _run systemctl is-active "$UNIT" >/dev/null 2>&1 && _warn "${UNIT} still active" || _log "${UNIT} stopped (or inactive)"
}

_backup_and_tune_env() {
  _log "=== backup .env + safer concurrency ==="
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing ${ENV_FILE} — aborting before start." >&2
    exit 1
  fi
  _run mkdir -p "$BACKUP_DIR"
  _run cp -a "$ENV_FILE" "${BACKUP_DIR}/.env"
  _log "backed up ${ENV_FILE} -> ${BACKUP_DIR}/.env"

  # Edit a temp copy then install, so a crash mid-edit leaves the original.
  local tmp
  tmp="$(_run mktemp "${BACKUP_DIR}/.env.work.XXXXXX")"
  _run cp -a "$ENV_FILE" "$tmp"
  # Ensure writable for upsert as current effective editor
  if [[ "${EUID}" -ne 0 ]]; then
    _run chown "$(id -u):$(id -g)" "$tmp" 2>/dev/null || true
  fi

  local pair key val
  for pair in "${SAFE_KEYS[@]}"; do
    key="${pair%%=*}"
    val="${pair#*=}"
    _set_kv "$key" "$val" "$tmp"
    _log "upsert ${key}=${val}"
  done

  _run cp -a "$tmp" "$ENV_FILE"
  rm -f "$tmp" 2>/dev/null || _run rm -f "$tmp"
  _log "applied safer concurrency to ${ENV_FILE}"
  grep -E '^(AUTOMATION_MAX_CONCURRENT_TASKS|MAX_CONCURRENT_OLLAMA_TASKS|ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE|ENTITY_PROFILE_BUILD_LIMIT)=' "$ENV_FILE" || true
}

_maybe_copy_debug() {
  if [[ "${SKIP_DEBUG_COPY:-0}" == "1" ]]; then
    _log "=== skip debug instrumentation copy (SKIP_DEBUG_COPY=1) ==="
    return 0
  fi
  _log "=== optional debug instrumentation ==="
  if [[ ! -d "$DEV_REPO_ROOT" ]]; then
    _warn "dev repo not present at ${DEV_REPO_ROOT} — skipping instrumentation copy"
    return 0
  fi

  local pair src_rel dst_rel src dst dst_dir
  local copied=0
  for pair in "${DEBUG_COPY_PAIRS[@]}"; do
    src_rel="${pair%%|*}"
    dst_rel="${pair##*|}"
    src="${DEV_REPO_ROOT}/${src_rel}"
    dst="${ROOT}/${dst_rel}"
    if [[ ! -f "$src" ]]; then
      _warn "missing source ${src} — skip"
      continue
    fi
    # Only copy when source contains the debug session marker (avoid blind overwrites).
    if ! grep -q '0b2a10\|#region agent log' "$src" 2>/dev/null; then
      _warn "${src_rel} has no debug marker — skip"
      continue
    fi
    dst_dir="$(dirname "$dst")"
    _run mkdir -p "$dst_dir" "$BACKUP_DIR/debug_prev"
    if [[ -f "$dst" ]]; then
      _run cp -a "$dst" "${BACKUP_DIR}/debug_prev/$(echo "$dst_rel" | tr '/' '_')"
    fi
    _run cp -a "$src" "$dst"
    _log "copied ${src_rel} -> ${dst}"
    copied=$((copied + 1))
  done
  if [[ "$copied" -eq 0 ]]; then
    _log "no instrumentation files copied"
  else
    _log "copied ${copied} instrumentation file(s); previous copies under ${BACKUP_DIR}/debug_prev"
  fi
}

_start_and_poll() {
  _log "=== start ${UNIT} ==="
  _run systemctl start "$UNIT"
  _log "polling health: ${HEALTH_URL} (${HEALTH_ATTEMPTS} x ${HEALTH_SLEEP_SEC}s)"

  local i
  for i in $(seq 1 "$HEALTH_ATTEMPTS"); do
    if curl -sf --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
      _log "health OK after ${i} attempt(s)"
      curl -s --max-time 5 "$HEALTH_URL" 2>/dev/null | head -c 400 || true
      echo
      # Best-effort readiness (do not fail recovery if readiness lags).
      if curl -sf --max-time 5 "$READINESS_URL" 2>/dev/null | grep -q '"ready"[[:space:]]*:[[:space:]]*true'; then
        _log "readiness: ready=true"
      else
        _warn "health up but readiness not yet true (may still be starting)"
      fi
      _run systemctl --no-pager -l status "$UNIT" || true
      return 0
    fi
    sleep "$HEALTH_SLEEP_SEC"
  done

  _warn "health did not respond within $((HEALTH_ATTEMPTS * HEALTH_SLEEP_SEC))s"
  _run systemctl --no-pager -l status "$UNIT" || true
  _run journalctl -u "$UNIT" -n 40 --no-pager || true
  return 1
}

main() {
  _require_rootish
  _log "Widow OOM recovery begin (root=${ROOT} unit=${UNIT})"
  _diagnose
  _stop_api
  _backup_and_tune_env
  _maybe_copy_debug
  _start_and_poll
  _log "Widow OOM recovery finished. Backup: ${BACKUP_DIR}"
  _log "No git commit/push performed. Review concurrency before raising again."
}

main "$@"
