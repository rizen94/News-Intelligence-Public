#!/usr/bin/env bash
#
# fix_monitoring_timeout.sh
#
# Patches the system monitoring routes to wrap all automation.get_status() calls
# in a timeout-protected helper, preventing the overview endpoint from hanging
# when the pipeline holds a lock.
#
# Usage:
#   ./fix_monitoring_timeout.sh [path/to/monitoring_routes.py]
#
# If no path is given, the script searches the working directory tree.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Locate the file ──────────────────────────────────────────────────────────

TARGET="${1:-}"

if [ -z "$TARGET" ]; then
    info "No file path provided — searching for monitoring routes file..."
    CANDIDATES=$(find . -type f -name "*.py" \
        | xargs grep -l 'prefix="/api/system_monitoring"' 2>/dev/null || true)

    COUNT=$(echo "$CANDIDATES" | grep -c '[^[:space:]]' || true)

    if [ "$COUNT" -eq 0 ]; then
        error "Could not find the monitoring routes file."
        error "Please provide the path as an argument:"
        error "  $0 path/to/system_monitoring_routes.py"
        exit 1
    elif [ "$COUNT" -gt 1 ]; then
        warn "Found multiple candidates:"
        echo "$CANDIDATES"
        TARGET=$(echo "$CANDIDATES" | head -1)
        warn "Using first match: $TARGET"
    else
        TARGET="$CANDIDATES"
    fi
fi

if [ ! -f "$TARGET" ]; then
    error "File not found: $TARGET"
    exit 1
fi

info "Target file: $TARGET"

# ── Back up ──────────────────────────────────────────────────────────────────

BACKUP="${TARGET}.bak.$(date +%Y%m%d_%H%M%S)"
cp "$TARGET" "$BACKUP"
info "Backup created: $BACKUP"

# ── Apply patches via Python ─────────────────────────────────────────────────

python3 - "$TARGET" << 'PATCH_SCRIPT'
import sys

filepath = sys.argv[1]

with open(filepath, "r") as f:
    content = f.read()

original = content  # keep a copy to verify changes happened
errors = []

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 1: Insert _safe_get_automation_status() before
#           _synthesize_current_activities_from_automation()
# ─────────────────────────────────────────────────────────────────────────────

NEW_HELPER = '''\
def _safe_get_automation_status(automation: Any | None, timeout: float = 2.0) -> dict[str, Any]:
    """Get automation status with timeout protection — never blocks the overview endpoint."""
    import queue as queue_module
    import threading

    mgr = _resolve_automation_for_monitor(automation)
    if mgr is None:
        return {}

    result_queue: queue_module.Queue = queue_module.Queue()

    def _run():
        try:
            result_queue.put(mgr.get_status())
        except Exception as e:
            logger.debug("_safe_get_automation_status: %s", e)
            result_queue.put({})

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if not result_queue.empty():
        try:
            return result_queue.get_nowait()
        except Exception:
            return {}
    logger.debug("_safe_get_automation_status timed out after %.1fs", timeout)
    return {}


'''

INSERTION_MARKER = "def _synthesize_current_activities_from_automation(automation: Any | None) -> list[dict[str, Any]]:"

if INSERTION_MARKER in content:
    # Only insert if the helper doesn't already exist (idempotent)
    if "def _safe_get_automation_status(" not in content:
        content = content.replace(INSERTION_MARKER, NEW_HELPER + INSERTION_MARKER, 1)
        print("[PATCH 1] Inserted _safe_get_automation_status()")
    else:
        print("[PATCH 1] _safe_get_automation_status() already present — skipped insertion")
else:
    errors.append("PATCH 1: Could not find _synthesize_current_activities_from_automation definition")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 2: Fix _synthesize_current_activities_from_automation to use the helper
# ─────────────────────────────────────────────────────────────────────────────

OLD_SYNTH = '''\
    mgr = _resolve_automation_for_monitor(automation)
    if mgr is None:
        return []
    try:
        st = mgr.get_status()
    except Exception:
        return []
    active = st.get("active_tasks_by_phase") or {}'''

NEW_SYNTH = '''\
    st = _safe_get_automation_status(automation, timeout=2.0)
    if not st:
        return []
    active = st.get("active_tasks_by_phase") or {}'''

if OLD_SYNTH in content:
    content = content.replace(OLD_SYNTH, NEW_SYNTH, 1)
    print("[PATCH 2] Fixed _synthesize_current_activities_from_automation()")
else:
    # Check if already patched
    if NEW_SYNTH in content:
        print("[PATCH 2] _synthesize_current_activities_from_automation() already patched — skipped")
    else:
        errors.append("PATCH 2: Could not find original code block in _synthesize_current_activities_from_automation")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 3: Fix _merge_current_activities_with_run_counts to use the helper
# ─────────────────────────────────────────────────────────────────────────────

OLD_MERGE = '''\
    active_by_phase: dict[str, int] = {}
    try:
        mgr = _resolve_automation_for_monitor(automation)
        if mgr is not None:
            active_by_phase = dict(mgr.get_status().get("active_tasks_by_phase") or {})
    except Exception:
        pass'''

NEW_MERGE = '''\
    active_by_phase: dict[str, int] = {}
    try:
        st = _safe_get_automation_status(automation, timeout=2.0)
        active_by_phase = dict(st.get("active_tasks_by_phase") or {})
    except Exception:
        pass'''

if OLD_MERGE in content:
    content = content.replace(OLD_MERGE, NEW_MERGE, 1)
    print("[PATCH 3] Fixed _merge_current_activities_with_run_counts()")
else:
    if NEW_MERGE in content:
        print("[PATCH 3] _merge_current_activities_with_run_counts() already patched — skipped")
    else:
        errors.append("PATCH 3: Could not find original code block in _merge_current_activities_with_run_counts")

# ─────────────────────────────────────────────────────────────────────────────
# PATCH 4: Simplify _get_processing_history_for_monitor to use the helper
# ─────────────────────────────────────────────────────────────────────────────

OLD_HISTORY = '''\
def _get_processing_history_for_monitor() -> dict[str, Any] | None:
    import queue as queue_module
    import threading

    result_queue: queue_module.Queue = queue_module.Queue()

    def _run():
        try:
            from services.automation_manager import get_automation_manager

            mgr = get_automation_manager()
            if mgr is None:
                result_queue.put(None)
                return
            status = mgr.get_status()
            metrics = status.get("metrics") or {}
            hist = metrics.get("processing_history")
            result_queue.put(hist if isinstance(hist, dict) else None)
        except Exception as e:
            logger.debug("monitor overview processing_history: %s", e)
            result_queue.put(None)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=MONITOR_OVERVIEW_AUTOMATION_HISTORY_TIMEOUT)
    if not result_queue.empty():
        try:
            return result_queue.get_nowait()
        except Exception:
            return None
    return None'''

NEW_HISTORY = '''\
def _get_processing_history_for_monitor() -> dict[str, Any] | None:
    st = _safe_get_automation_status(None, timeout=MONITOR_OVERVIEW_AUTOMATION_HISTORY_TIMEOUT)
    if not st:
        return None
    metrics = st.get("metrics") or {}
    hist = metrics.get("processing_history")
    return hist if isinstance(hist, dict) else None'''

if OLD_HISTORY in content:
    content = content.replace(OLD_HISTORY, NEW_HISTORY, 1)
    print("[PATCH 4] Simplified _get_processing_history_for_monitor()")
else:
    if NEW_HISTORY in content:
        print("[PATCH 4] _get_processing_history_for_monitor() already patched — skipped")
    else:
        errors.append("PATCH 4: Could not find original code block in _get_processing_history_for_monitor")

# ─────────────────────────────────────────────────────────────────────────────
# Write result
# ─────────────────────────────────────────────────────────────────────────────

if errors:
    print()
    for e in errors:
        print(f"ERROR: {e}")
    print()
    print("Aborting — no changes written. The file may have already been modified")
    print("or the code doesn't match what was expected. Check the backup and apply manually.")
    sys.exit(1)

if content == original:
    print("\nNo changes needed — file already up to date.")
    sys.exit(0)

with open(filepath, "w") as f:
    f.write(content)

print("\nAll patches applied successfully.")
PATCH_SCRIPT

PATCH_EXIT=$?

if [ $PATCH_EXIT -ne 0 ]; then
    error "Patch script failed (exit $PATCH_EXIT). Restoring backup..."
    cp "$BACKUP" "$TARGET"
    error "Original file restored from $BACKUP"
    exit 1
fi

# ── Verify syntax ────────────────────────────────────────────────────────────

info "Verifying Python syntax..."
if python3 -c "
import ast, sys
try:
    with open(sys.argv[1]) as f:
        ast.parse(f.read())
    print('Syntax OK')
except SyntaxError as e:
    print(f'Syntax error: {e}')
    sys.exit(1)
" "$TARGET"; then
    info "Syntax check passed."
else
    error "Syntax check FAILED. Restoring backup..."
    cp "$BACKUP" "$TARGET"
    error "Original file restored from $BACKUP"
    exit 1
fi

# ── Verify the patches are present ──────────────────────────────────────────

info "Verifying patches..."
VERIFY_OK=true

if ! grep -q "def _safe_get_automation_status" "$TARGET"; then
    error "Missing: _safe_get_automation_status function"
    VERIFY_OK=false
fi

if grep -q "mgr = _resolve_automation_for_monitor(automation)" "$TARGET"; then
    # This line should only appear inside _safe_get_automation_status now,
    # not in the two consumer functions. Count occurrences.
    COUNT=$(grep -c "mgr = _resolve_automation_for_monitor(automation)" "$TARGET" || true)
    if [ "$COUNT" -gt 1 ]; then
        error "Found $COUNT direct _resolve_automation_for_monitor calls (expected 1 in _safe_get_automation_status only)"
        VERIFY_OK=false
    fi
fi

if grep -q "mgr.get_status().get(\"active_tasks_by_phase\")" "$TARGET"; then
    error "Found unprotected mgr.get_status() call still in _merge function"
    VERIFY_OK=false
fi

if [ "$VERIFY_OK" = false ]; then
    error "Verification failed. Restoring backup..."
    cp "$BACKUP" "$TARGET"
    error "Original file restored from $BACKUP"
    exit 1
fi

info "All verifications passed."

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
info "═══════════════════════════════════════════════════════════════"
info " Fix applied successfully"
info "═══════════════════════════════════════════════════════════════"
info ""
info " What changed:"
info "  1. Added _safe_get_automation_status() — wraps get_status()"
info "     in a daemon thread with a 2-second timeout"
info "  2. _synthesize_current_activities_from_automation() now uses"
info "     the safe helper instead of calling get_status() directly"
info "  3. _merge_current_activities_with_run_counts() now uses"
info "     the safe helper instead of calling get_status() directly"
info "  4. _get_processing_history_for_monitor() simplified to use"
info "     the same safe helper (was already timeout-wrapped but"
info "     duplicated the logic)"
info ""
info " Backup: $BACKUP"
info ""
info " To verify in production:"
info "   1. Restart the API server"
info "   2. Trigger a heavy pipeline phase (e.g. entity_extraction)"
info "   3. Load the Monitor page — it should respond in <6s even"
info "      while the pipeline is busy"
info ""
info " To revert:"
info "   cp $BACKUP $TARGET"
info ""
