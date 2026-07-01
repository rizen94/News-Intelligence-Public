#!/usr/bin/env bash
# Live progress bars for bulk catch-up (event → context_sync → content_enrichment chain).
ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
cd "$ROOT" || exit 1
INTERVAL="${1:-30}"
exec .venv/bin/python3 api/scripts/bulk_catchup_status.py --progress --watch "$INTERVAL"
