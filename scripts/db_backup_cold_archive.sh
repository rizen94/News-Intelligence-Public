#!/bin/bash
# Copy latest monthly backup to cold archive path (off-site / second disk).
# Run after db_backup_monthly.sh on the 1st, or weekly as operator policy allows.

set -euo pipefail

_REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$_REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$_REPO_ROOT/.env"
  set +a
fi

BACKUP_MONTHLY_DIR="${BACKUP_MONTHLY_DIR:-/opt/news-intelligence/backups/monthly}"
BACKUP_COLD_DIR="${BACKUP_COLD_DIR:-${NAS_BACKUP_PATH:-}/database-backup/cold}"

if [ -z "${BACKUP_COLD_DIR}" ] || [ "${BACKUP_COLD_DIR}" = "/database-backup/cold" ]; then
  echo "Set BACKUP_COLD_DIR or NAS_BACKUP_PATH for cold archive destination" >&2
  exit 1
fi

LATEST="$(ls -1t "${BACKUP_MONTHLY_DIR}"/news_intel_*.pgdump 2>/dev/null | head -1 || true)"
if [ -z "${LATEST}" ]; then
  echo "No monthly backup found in ${BACKUP_MONTHLY_DIR}" >&2
  exit 1
fi

mkdir -p "${BACKUP_COLD_DIR}"
DEST="${BACKUP_COLD_DIR}/$(basename "${LATEST}")"
echo "[$(date -Iseconds)] Cold archive copy ${LATEST} → ${DEST}"
cp -a "${LATEST}" "${DEST}.tmp.$$"
mv -f "${DEST}.tmp.$$" "${DEST}"
echo "[$(date -Iseconds)] Done $(du -h "${DEST}" | awk '{print $1}')"
