#!/usr/bin/env bash
# api_restart_metrics.sh — Track API service restart timing metrics.
#
# Usage:
#   # Record start (call before restart):
#   scripts/api_restart_metrics.sh record-start
#
#   # Wait for readiness and log final metrics (call after restart):
#   scripts/api_restart_metrics.sh record-ready
#
# Metrics are persisted to /var/run/news-intelligence/api_restart_metrics.json.
# Each entry captures: start_ts, ready_ts, duration_sec, readiness_attempts, status.
set -euo pipefail

# Configuration (override via env or defaults)
API_UNIT="${API_UNIT:-news-intelligence-api-public.service}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/system_monitoring/health}"
READINESS_URL="${NI_READINESS_URL:-http://127.0.0.1:8000/api/system_monitoring/startup/readiness}"
MAX_ATTEMPTS="${NI_READINESS_ATTEMPTS:-24}"
SLEEP_SEC="${NI_READINESS_SLEEP_SEC:-2}"
RUN_DIR="${DISK_IO_PRESSURE_RUN_DIR:-/run/news-intelligence}"
METRICS_FILE="${RUN_DIR}/api_restart_metrics.json"
START_TS_FILE="${RUN_DIR}/api_restart_start_ts"
LOG_DIR="${LOG_DIR:-/var/log/news-intelligence}"
LOG_FILE="${LOG_DIR}/restart-metrics.log"

mkdir -p "$RUN_DIR" "$LOG_DIR"

log() {
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "$ts $*" | tee -a "$LOG_FILE"
}

# JSON helper: append an entry to the metrics file (append-only, no jq needed)
record_metric() {
  local start_ts="$1" ready_ts="$2" duration="$3" attempts="$4" status="$5" reason="${6:-ok}"

  # Create file if it doesn't exist with root array
  if [[ ! -f "$METRICS_FILE" ]] || [[ $(cat "$METRICS_FILE" 2>/dev/null) == "" ]]; then
    echo '[]' > "$METRICS_FILE"
  fi

  # Append entry (maintains valid JSON array)
  local tmp_file="${METRICS_FILE}.tmp"
  local current original_content
  
  original_content=$(cat "$METRICS_FILE")
  
  # Remove trailing ']' to prepare for append
  current="${original_content%]}"

  # Add comma separator only if there was already data (not the initial [])
  if [[ -n "$original_content" && "$original_content" != "[]" ]]; then
    current="${current},"
  fi

  # Sanitize fields for valid JSON: empty timestamps → bare null, populated → quoted strings
  local is_start_empty=false is_ready_empty=false
  [[ -z "$start_ts" ]] && is_start_empty=true
  [[ -z "$ready_ts" ]] && is_ready_empty=true
  start_ts="${start_ts:-unknown}"
  ready_ts="${ready_ts:-unknown}"
  
  local j_start_ts j_ready_ts
  if $is_start_empty; then j_start_ts='null'; else j_start_ts="\"$start_ts\""; fi
  if $is_ready_empty; then j_ready_ts='null'; else j_ready_ts="\"$ready_ts\""; fi
  
  # Numeric defaults for duration and attempts
  local dur_val="${duration:-0}" att_val="${attempts:-0}"

  # Append new entry
  cat >> "$tmp_file" <<ENTRY_EOF
[${current}{
  "timestamp": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "service": "$API_UNIT",
  "restart_start": $j_start_ts,
  "restart_ready": $j_ready_ts,
  "duration_sec": $dur_val,
  "readiness_attempts": $att_val,
  "status": "${status}",
  "reason": "${reason}"
}]
ENTRY_EOF

  mv "$tmp_file" "$METRICS_FILE"

  # Trim to last 100 entries to prevent unbounded growth
  if [[ $(wc -l < "$METRICS_FILE") -gt 500 ]]; then
    # Keep only last N complete objects (~8 lines each)
    tail -400 "$METRICS_FILE" > "${METRICS_FILE}.trimmed"
    mv "${METRICS_FILE}.trimmed" "$METRICS_FILE"
  fi
}

cmd_record_start() {
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  date +%s > "$START_TS_FILE"
  echo "$ts" >> "$START_TS_FILE"
  log "RECORD-START: service=$API_UNIT timestamp=$ts epoch=$(date +%s)"

  # Output for piping/consumers
  echo "{\"event\":\"record_start\",\"timestamp\":\"$ts\",\"epoch\":$(date +%s)}"
}

cmd_record_ready() {
  local start_epoch ready_epoch duration attempts=0 status="ready" reason="ok"

  # Check for start timestamp file
  if [[ ! -f "$START_TS_FILE" ]]; then
    log "WARNING: No start timestamp found — recording as standalone ready event"
    start_epoch=$(date +%s)
    local start_ts
    start_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  else
    # Use the last recorded epoch from start (in case multiple started events exist)
    start_epoch=$(tail -1 "$START_TS_FILE" | grep -E '^[0-9]+$' || echo "$(date +%s)")
    local start_ts
    start_ts=$(head -1 "$START_TS_FILE")
  fi

  log "RECORD-READY: Waiting for readiness endpoint..."

  # Poll readiness endpoint (same logic as systemd_wait_readiness.sh)
  for i in $(seq 1 "$MAX_ATTEMPTS"); do
    attempts=$i
    if response=$(curl -sf --max-time 3 "$READINESS_URL" 2>/dev/null); then
      if echo "$response" | grep -q '"ready"[[:space:]]*:[[:space:]]*true'; then
        ready_epoch=$(date +%s)
        local ready_ts
        ready_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        duration=$((ready_epoch - start_epoch))

        log "RECORD-READY: service=$API_UNIT ready in ${duration}s after ${attempts} attempts"

        # Record the metric
        record_metric "$start_ts" "$ready_ts" "$duration" "$attempts" "$status" "$reason"

        echo "{\"event\":\"record_ready\",\"duration_sec\":$duration,\"attempts\":$attempts,\"status\":\"$status\"}"

        # Clean up start file so we don't accumulate stale data
        rm -f "$START_TS_FILE"
        return 0
      fi
    fi
    sleep "$SLEEP_SEC"
  done

  # If we get here, readiness timed out
  ready_epoch=$(date +%s)
  local ready_ts
  ready_ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  duration=$((ready_epoch - start_epoch))
  status="timed_out"
  reason="readiness_endpoint_not_healthy_after_${MAX_ATTEMPTS}_attempts"

  log "RECORD-READY: service=$API_UNIT FAILED to become ready in ${duration}s after ${attempts} attempts (status=$status)"
  record_metric "$start_ts" "$ready_ts" "$duration" "$attempts" "$status" "$reason"

  echo "{\"event\":\"record_ready\",\"duration_sec\":$duration,\"attempts\":$attempts,\"status\":\"$status\",\"reason\":\"$reason\"}"
  return 1
}

cmd_show_summary() {
  if [[ ! -f "$METRICS_FILE" ]]; then
    echo "No metrics recorded yet."
    return 0
  fi

  local total count max_duration min_duration avg_duration last_status
  total=$(wc -l < "$METRICS_FILE")
  count=$(grep -o '"duration_sec"' "$METRICS_FILE" | wc -l)

  if [[ $count -eq 0 ]]; then
    echo "No valid metrics entries found."
    return 0
  fi

  # Extract durations for stats
  local durations
  durations=$(grep -o '"duration_sec": *[0-9]*' "$METRICS_FILE" | grep -o '[0-9]*$')

  max_duration=0
  min_duration=999999
  sum=0

  while read -r d; do
    [[ -z "$d" ]] && continue
    if (( d > max_duration )); then max_duration=$d; fi
    if (( d < min_duration )); then min_duration=$d; fi
    sum=$((sum + d))
  done <<< "$durations"

  if [[ $count -gt 0 ]]; then
    avg_duration=$((sum / count))
  else
    avg_duration=0
  fi

  last_status=$(grep -o '"status":"[a-z]*"' "$METRICS_FILE" | tail -1)

  echo "=== API Restart Metrics Summary ==="
  echo "Total restarts tracked: $count"
  echo "Min duration: ${min_duration}s"
  echo "Max duration: ${max_duration}s"
  echo "Avg duration: ${avg_duration}s"
  echo "Last status:  ${last_status}"
  echo "Metrics file: $METRICS_FILE"
}

cmd_clear_metrics() {
  if [[ -f "$METRICS_FILE" ]]; then
    rm -f "$METRICS_FILE"
    log "CLEARED: Metrics file reset"
    echo "Metrics cleared."
  else
    echo "No metrics file to clear."
  fi
}

cmd_reset_cooldown() {
  local COOLDOWN_FILE="${RUN_DIR}/api_health_watchdog_cooldown"
  if [[ -f "$COOLDOWN_FILE" ]]; then
    rm -f "$COOLDOWN_FILE"
    log "CLEARED: Watchdog cooldown reset"
    echo "Cooldown cleared."
  else
    echo "No cooldown file to clear."
  fi
}

# CLI dispatch
case "${1:-}" in
  record-start)
    cmd_record_start
    ;;
  record-ready)
    cmd_record_ready
    ;;
  show-summary|summary)
    cmd_show_summary
    ;;
  clear-metrics)
    cmd_clear_metrics
    ;;
  reset-cooldown)
    cmd_reset_cooldown
    ;;
  *)
    echo "Usage: $0 {record-start|record-ready|show-summary|clear-metrics|reset-cooldown}"
    exit 1
    ;;
esac
