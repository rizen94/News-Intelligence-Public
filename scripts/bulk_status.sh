#!/usr/bin/env bash
# Quick bulk / pipeline status (run from any terminal on Widow).
ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
cd "$ROOT" || exit 1
exec .venv/bin/python3 api/scripts/bulk_catchup_status.py "$@"
