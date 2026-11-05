#!/usr/bin/env bash
# Wait-then-start targeted entity_profile_build burn on PopOS refine worker.
#
# Trigger conditions (all must pass):
#   1) CTF pending <= CTF_PENDING_MAX (default 100) OR Widow CTF burn log ends with DONE
#   2) Editorial story_continuation has no "pool exhausted" for HEALTHY_MINUTES (default 5)
#      — refine (profiles) and editorial (continuation) may overlap when the pool is healthy
#
# On trigger: write refine drop-in (entity_profile_build only), daemon-reload, restart refine.
# Leaves content_refinement_queue OFF the burn worker so profiles are not starved by 70b finisher.
#
# Restore after burn (preferred):
#   /tmp/entity_profile_burn_RESTORE.sh
#   # clears refine burn drop-in + restarts claim-topic/uie/assembly/editorial
#   # refine returns to: entity_profile_build,content_refinement_queue (unit defaults)
#
# Manual refine-only restore:
#   rm -f ~/.config/systemd/user/news-intelligence-popos-worker-refine.service.d/entity-profile-burn.conf
#   systemctl --user daemon-reload
#   systemctl --user restart news-intelligence-popos-worker-refine.service
#
# Optional: clear editorial continuation burn drop-in when that backlog is drained:
#   rm -f ~/.config/systemd/user/news-intelligence-popos-worker-editorial.service.d/continuation-burn.conf
#   systemctl --user daemon-reload && systemctl --user restart news-intelligence-popos-worker-editorial.service
#
# Contention pause (GPU monopoly for profiles): stop claim-topic, uie, assembly, editorial;
# leave refine running. Unit list: /tmp/entity_profile_burn_contention_paused.units

set -euo pipefail

ROOT="${NI_ROOT:-/home/pete/ni-popos-worker}"
VENV="${ROOT}/.venv/bin/python"
UNIT_REFINE="news-intelligence-popos-worker-refine.service"
UNIT_EDITORIAL="news-intelligence-popos-worker-editorial.service"
DROPIN_DIR="${HOME}/.config/systemd/user/${UNIT_REFINE}.d"
DROPIN="${DROPIN_DIR}/entity-profile-burn.conf"
LOG="${ENTITY_PROFILE_BURN_WAIT_LOG:-/tmp/entity_profile_burn_wait.log}"
PIDFILE="${ENTITY_PROFILE_BURN_WAIT_PID:-/tmp/entity_profile_burn_wait.pid}"

CTF_PENDING_MAX="${CTF_PENDING_MAX:-100}"
HEALTHY_MINUTES="${HEALTHY_MINUTES:-5}"
POLL_SECONDS="${POLL_SECONDS:-30}"
WIDOW_HOST="${WIDOW_HOST:-pete@192.168.93.101}"
CTF_LOG_REMOTE="${CTF_LOG_REMOTE:-/opt/news-intelligence/logs/claims_to_facts_burn.log}"

ENTITY_PROFILE_BUILD_LIMIT="${ENTITY_PROFILE_BUILD_LIMIT:-60}"
ENTITY_PROFILE_BUILD_PARALLEL="${ENTITY_PROFILE_BUILD_PARALLEL:-6}"
ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE="${ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE:-30}"
IDLE_SLEEP="${IDLE_SLEEP:-5}"
BUDGET_SECONDS="${BUDGET_SECONDS:-3600}"

mkdir -p "$(dirname "$LOG")" "$DROPIN_DIR"
echo $$ >"$PIDFILE"
exec >>"$LOG" 2>&1

log() { printf '%s %s\n' "$(date -Iseconds)" "$*"; }

ctf_pending() {
  set -a
  # shellcheck disable=SC1091
  [[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
  # shellcheck disable=SC1091
  [[ -f "$ROOT/.env.popos_worker" ]] && source "$ROOT/.env.popos_worker"
  set +a
  PYTHONPATH="$ROOT/api" "$VENV" - <<'PY'
from services.backlog_metrics import _count_claims_to_facts_pending
print(int(_count_claims_to_facts_pending() or 0))
PY
}

ctf_oneshot_done() {
  ssh -o ConnectTimeout=8 -o BatchMode=yes "$WIDOW_HOST" \
    "tail -n 5 '$CTF_LOG_REMOTE' 2>/dev/null | grep -q '^DONE '" \
    && return 0
  return 1
}

pool_healthy() {
  local since
  since="$(date -d "${HEALTHY_MINUTES} minutes ago" '+%Y-%m-%d %H:%M:%S' 2>/dev/null \
    || date -v-"${HEALTHY_MINUTES}"M '+%Y-%m-%d %H:%M:%S')"
  if journalctl --user -u "$UNIT_EDITORIAL" --since "$since" --no-pager 2>/dev/null \
    | grep -q 'pool exhausted'; then
    return 1
  fi
  return 0
}

entity_backlog() {
  set -a
  # shellcheck disable=SC1091
  [[ -f "$ROOT/.env" ]] && source "$ROOT/.env"
  # shellcheck disable=SC1091
  [[ -f "$ROOT/.env.popos_worker" ]] && source "$ROOT/.env.popos_worker"
  set +a
  PYTHONPATH="$ROOT/api" "$VENV" - <<'PY'
from services.backlog_metrics import _count_entity_profile_build_backlog
print(int(_count_entity_profile_build_backlog() or 0))
PY
}

write_dropin() {
  cat >"$DROPIN" <<EOF
[Service]
# Targeted entity_profile_build burn (content_refinement_queue intentionally omitted)
ExecStart=
ExecStart=${ROOT}/.venv/bin/python ${ROOT}/scripts/run_popos_phase_worker.py --worker-id refine --phases entity_profile_build --idle-sleep ${IDLE_SLEEP} --budget-seconds ${BUDGET_SECONDS}
Environment=ENTITY_PROFILE_BUILD_LIMIT=${ENTITY_PROFILE_BUILD_LIMIT}
Environment=ENTITY_PROFILE_BUILD_PARALLEL=${ENTITY_PROFILE_BUILD_PARALLEL}
Environment=ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE=${ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE}
Environment=ENTITY_PROFILE_BUILD_DRAIN=true
Environment=ENTITY_PROFILE_BUILD_ANYTIME=true
EOF
}

start_burn() {
  write_dropin
  systemctl --user daemon-reload
  systemctl --user restart "$UNIT_REFINE"
  sleep 2
  systemctl --user --no-pager status "$UNIT_REFINE" | head -20 || true
  log "BURN_STARTED drop-in=$DROPIN limit=$ENTITY_PROFILE_BUILD_LIMIT parallel=$ENTITY_PROFILE_BUILD_PARALLEL"
  log "RESTORE: rm -f $DROPIN && systemctl --user daemon-reload && systemctl --user restart $UNIT_REFINE"
}

log "=== entity_profile_build burn waiter start pid=$$ ==="
log "CTF_PENDING_MAX=$CTF_PENDING_MAX HEALTHY_MINUTES=$HEALTHY_MINUTES POLL_SECONDS=$POLL_SECONDS"
log "burn knobs LIMIT=$ENTITY_PROFILE_BUILD_LIMIT PARALLEL=$ENTITY_PROFILE_BUILD_PARALLEL LLM_BATCH=$ENTITY_PROFILE_BUILD_LLM_BATCH_SIZE"

# If drop-in already active with entity_profile_build-only, exit cleanly.
if [[ -f "$DROPIN" ]] && systemctl --user show "$UNIT_REFINE" -p ActiveState --value 2>/dev/null | grep -qx active; then
  if systemctl --user show "$UNIT_REFINE" -p ExecStart --value 2>/dev/null | grep -q 'phases entity_profile_build[^-]'; then
    if ! systemctl --user show "$UNIT_REFINE" -p ExecStart --value 2>/dev/null | grep -q content_refinement; then
      log "ALREADY_BURNING refine drop-in present — exiting"
      exit 0
    fi
  fi
fi

while true; do
  ctf_ok=0
  pool_ok=0
  ctf_n="?"
  if ctf_n="$(ctf_pending 2>/dev/null | tail -1)"; then
    if [[ "$ctf_n" =~ ^[0-9]+$ ]] && (( ctf_n <= CTF_PENDING_MAX )); then
      ctf_ok=1
    fi
  else
    ctf_n="err"
  fi
  if (( ctf_ok == 0 )) && ctf_oneshot_done; then
    ctf_ok=1
    ctf_n="${ctf_n}+DONE"
  fi

  if pool_healthy; then
    pool_ok=1
  fi

  ep_n="?"
  ep_n="$(entity_backlog 2>/dev/null | tail -1 || echo err)"

  log "poll ctf_pending=$ctf_n ctf_ok=$ctf_ok pool_ok=$pool_ok entity_profile_pending=$ep_n"

  if (( ctf_ok == 1 && pool_ok == 1 )); then
    log "TRIGGERS_MET — starting entity_profile_build burn"
    start_burn
    log "=== waiter complete ==="
    exit 0
  fi

  sleep "$POLL_SECONDS"
done
