#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/pete/Documents/projects/Projects/News Intelligence"
VENV="${PROJECT_DIR}/.venv/bin/python"
SCRIPT="${PROJECT_DIR}/scripts/preseed_wikipedia_cache.py"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/wikipedia_preseed_$(date +%Y%m%d_%H%M%S).log"

export DB_HOST="192.168.93.101"
export DB_PORT="5432"
export DB_NAME="news_intel"
export DB_USER="newsapp"
export DB_PASSWORD="v4xB--yiRtQ5b1eact_l5K7jnq6mVPtw"

mkdir -p "${LOG_DIR}"

echo "=== Wikipedia pre-seed started at $(date) ===" >> "${LOG_FILE}"
"${VENV}" "${SCRIPT}" --types person organization --search-fallback >> "${LOG_FILE}" 2>&1
EXIT_CODE=$?
echo "=== Finished at $(date) with exit code ${EXIT_CODE} ===" >> "${LOG_FILE}"

find "${LOG_DIR}" -name "wikipedia_preseed_*.log" -mtime +30 -delete 2>/dev/null || true
exit ${EXIT_CODE}
