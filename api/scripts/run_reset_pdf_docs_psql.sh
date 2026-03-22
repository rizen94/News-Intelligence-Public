#!/usr/bin/env bash
# Run reset_pdf_parser_failed_documents.sql using DB_* from repo-root .env.
# Usage (from repo root):
#   bash api/scripts/run_reset_pdf_docs_psql.sh
#
# Requires: psql client installed, network path to DB, valid .env.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SQL="$ROOT/api/scripts/sql/reset_pdf_parser_failed_documents.sql"
if [[ ! -f "$SQL" ]]; then
  echo "Missing $SQL" >&2
  exit 1
fi
if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env (need DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a
: "${DB_HOST:?DB_HOST not set}"
: "${DB_PORT:?DB_PORT not set}"
: "${DB_NAME:?DB_NAME not set}"
: "${DB_USER:?DB_USER not set}"
: "${DB_PASSWORD:?DB_PASSWORD not set}"
export PGPASSWORD="$DB_PASSWORD"
exec psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$SQL"
