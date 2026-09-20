#!/usr/bin/env bash
# Apply steady-state prescreening env on Widow (idempotent).
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
ENV_FILE="$ROOT/.env"

_set_kv() {
  local key="$1"
  local val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >>"$ENV_FILE"
  fi
}

echo "=== Applying prescreening env to $ENV_FILE ==="
_set_kv RSS_INGEST_MIN_QUALITY_SCORE "0.38"
_set_kv ARTICLE_SIGNAL_ENABLED "true"
_set_kv ARTICLE_SIGNAL_FULL_MIN_QUALITY "0.50"
_set_kv COLLECTION_THROTTLE_PENDING_THRESHOLD "800"
_set_kv RSS_FEED_SILENCE_ENABLED "true"
_set_kv RSS_FEED_SILENCE_DRY_RUN "false"
_set_kv RSS_FEED_SILENCE_MIN_QUALITY "0.50"
_set_kv PIPELINE_REFINEMENT_ANYTIME "false"

grep -E "^(RSS_INGEST_MIN_QUALITY|ARTICLE_SIGNAL|COLLECTION_THROTTLE|RSS_FEED_SILENCE|PIPELINE_REFINEMENT)" "$ENV_FILE" || true
echo "Done. Restart API after code deploy: sudo systemctl restart news-intelligence-api-public"
