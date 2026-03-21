#!/usr/bin/env bash
# Dynamic DNS update for DuckDNS — run on Widow (or any host on the LAN that shares the WAN IP).
# See docs/DYNAMIC_DNS_WIDOW.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${DDNS_ENV_FILE:-${REPO_ROOT}/configs/ddns.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  set -a
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${DUCKDNS_DOMAIN:-}" || -z "${DUCKDNS_TOKEN:-}" ]]; then
  echo "ddns_update_duckdns: set DUCKDNS_DOMAIN and DUCKDNS_TOKEN in ${ENV_FILE} or environment." >&2
  exit 1
fi

# Omit ip= so DuckDNS uses the request source address (your WAN IP when egress is via the home router).
url="https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}"
out="$(curl -fsS --max-time 30 "${url}")" || {
  echo "ddns_update_duckdns: curl failed" >&2
  exit 1
}

echo "$(date -Iseconds) duckdns: ${out}"
if [[ "${out}" == "OK" ]]; then
  exit 0
fi
if [[ "${out}" == "KO" ]]; then
  echo "ddns_update_duckdns: DuckDNS returned KO (check domain/token)" >&2
  exit 1
fi
echo "ddns_update_duckdns: unexpected response: ${out}" >&2
exit 1
