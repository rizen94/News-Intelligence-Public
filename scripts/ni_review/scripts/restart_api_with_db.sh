#!/bin/bash
# DEPRECATED LOCATION — thin wrapper only.
# Canonical script: repo root scripts/restart_api_with_db.sh (Widow-first DB, port-based stop, safe pkill).
# The obsolete copy that lived here is archived under scripts/ni_review/scripts/archive_deprecated/
# as restart_api_with_db.sh.deprecated-pre-2026-04-17
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/../../restart_api_with_db.sh" "$@"
