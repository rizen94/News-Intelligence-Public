#!/usr/bin/env bash
# Revert temporary catch-up env on Widow (after nightly window or manual stop).
set -euo pipefail
WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"
REMOTE_DIR="${REMOTE_DIR:-/opt/news-intelligence}"

ssh "${WIDOW_USER}@${WIDOW_HOST}" "bash -s" <<REMOTE
set -euo pipefail
cd "${REMOTE_DIR}"
latest=\$(ls -t .env.bak.catchup_* 2>/dev/null | head -1 || true)
if [[ -z "\$latest" ]]; then
  echo "No .env.bak.catchup_* found — restore keys manually."
  exit 1
fi
cp -a "\$latest" .env
grep -E '^(NIGHTLY_PIPELINE_ALL_DAY|NIGHTLY_PIPELINE_EXCLUSIVE|PIPELINE_QUIET)' .env | head -5
sudo systemctl restart news-intelligence-api-public
echo "Restored .env from \$latest and restarted API."
REMOTE