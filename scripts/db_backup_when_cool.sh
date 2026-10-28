#!/bin/bash
set -euo pipefail
OPT=/opt/news-intelligence
LOG=$OPT/logs/backup.log
mkdir -p "$OPT/logs"
exec >>"$LOG" 2>&1
echo "[$(date -Iseconds)] when_cool watcher started"
for i in $(seq 1 36); do
  if python3 - <<PY
import json, time
from datetime import datetime
p = "/run/news-intelligence/disk_io_pressure.json"
try:
    d = json.load(open(p))
    ts = datetime.fromisoformat((d.get("updated_at") or d["written_at"]).replace("Z", "+00:00")).timestamp()
    if time.time() - ts > 120:
        raise SystemExit(0)
    raise SystemExit(0 if not d.get("defer_heavy_writes") else 1)
except Exception:
    raise SystemExit(0)
PY
  then
    echo "[$(date -Iseconds)] pressure clear — starting backup (attempt after wait loop $i)"
    exec "$OPT/scripts/db_backup_single_latest.sh"
  fi
  echo "[$(date -Iseconds)] USB still hot; sleep 5m (loop $i/36)"
  sleep 300
done
echo "[$(date -Iseconds)] gave up waiting for IO clear"
exit 1
