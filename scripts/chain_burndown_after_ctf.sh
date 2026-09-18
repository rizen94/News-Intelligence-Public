#!/usr/bin/env bash
# Wait for CTF burndown to finish, then burn graph_link_drift_review and
# storyline_membership_review (auto-tune catch-up on PopOS).
#
# Usage:
#   scripts/chain_burndown_after_ctf.sh
#   CTF_PID=40335 scripts/chain_burndown_after_ctf.sh
#   CTF_LOG=/path/to/ctf.log scripts/chain_burndown_after_ctf.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LINK="${HOME}/ni-popos-worker"
VENV="${LINK}/.venv/bin/python"
[[ -x "$VENV" ]] || VENV="${ROOT}/.venv/bin/python"
LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"

# Prefer explicit PID; else newest b2000/b1000 CTF process; else wait on log "done"
CTF_PID="${CTF_PID:-}"
if [[ -z "$CTF_PID" ]]; then
  CTF_PID="$(pgrep -f 'venv/bin/python.*burn_down_claims_to_facts' | head -1 || true)"
fi

CHAIN_LOG="${LOG_DIR}/burndown_chain_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$CHAIN_LOG") 2>&1
echo "[chain] log=$CHAIN_LOG root=$ROOT ctf_pid=${CTF_PID:-none}"

set -a
[[ -f "$ROOT/.env" ]] && . "$ROOT/.env"
[[ -f "$ROOT/.env.popos_worker" ]] && . "$ROOT/.env.popos_worker"
[[ -f "${LINK}/.env" ]] && . "${LINK}/.env"
[[ -f "${LINK}/.env.popos_worker" ]] && . "${LINK}/.env.popos_worker"
set +a
if [[ -z "${DB_PASSWORD:-}" && -f "$ROOT/.db_password_widow" ]]; then
  DB_PASSWORD="$(head -1 "$ROOT/.db_password_widow")"
  export DB_PASSWORD
fi
export PYTHONPATH="${ROOT}/api"
export ADAPTIVE_BATCH_ENABLED="${ADAPTIVE_BATCH_ENABLED:-true}"
export GRAPH_LINK_DRIFT_REVIEW_ENABLED=true
export STORYLINE_MEMBERSHIP_REVIEW_ENABLED="${STORYLINE_MEMBERSHIP_REVIEW_ENABLED:-true}"
export STORYLINE_MEMBERSHIP_REVIEW_DRY_RUN=false

if [[ -n "$CTF_PID" ]] && kill -0 "$CTF_PID" 2>/dev/null; then
  echo "[chain] waiting for CTF burndown pid=$CTF_PID …"
  while kill -0 "$CTF_PID" 2>/dev/null; do
    sleep 30
  done
  echo "[chain] CTF pid=$CTF_PID exited"
else
  echo "[chain] no live CTF process — proceeding to next phases"
fi

HOURS="${CATCHUP_HOURS:-3}"
BATCH_CAP="${CATCHUP_BATCH_CAP:-2000}"
PHASE_LOG="${LOG_DIR}/phase_burndown_$(date +%Y%m%d_%H%M%S).log"
echo "[chain] starting graph_link_drift_review + storyline_membership_review hours=$HOURS batch_cap=$BATCH_CAP"
echo "[chain] phase_log=$PHASE_LOG"

"$VENV" "$ROOT/api/scripts/burn_down_phase_catchup.py" \
  --phases graph_link_drift_review,storyline_membership_review \
  --hours "$HOURS" \
  --batch-cap "$BATCH_CAP" \
  --auto \
  --log-file "$PHASE_LOG"

echo "[chain] finished OK"
