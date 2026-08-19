#!/usr/bin/env bash
# Removes the broken system-level unit left from the space/%20 experiment.
# The live worker is: systemctl --user status news-intelligence-popos-worker
set -euo pipefail
UNIT=/etc/systemd/system/news-intelligence-popos-worker.service
if [[ -f "$UNIT" ]]; then
  sudo rm -f "$UNIT"
  echo "Removed $UNIT"
else
  echo "Already gone: $UNIT"
fi
sudo systemctl daemon-reload
sudo systemctl reset-failed news-intelligence-popos-worker 2>/dev/null || true
echo "system unit status (expect: not-found or inactive, not bad-setting):"
systemctl status news-intelligence-popos-worker --no-pager 2>&1 | head -8 || true
echo
echo "live worker:"
systemctl --user is-active news-intelligence-popos-worker
systemctl --user status news-intelligence-popos-worker --no-pager 2>&1 | head -12
