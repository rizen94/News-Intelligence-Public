#!/usr/bin/env bash
# Smoke test for the Filesystem MCP allowlist defined in
# .continue/mcpServers/filesystem.yaml.
#
# Exits 0 if:
#   - read_file on an in-allowlist file SUCCEEDS, AND
#   - read_file on an out-of-allowlist file is REFUSED.
#
# Run from the workspace root:
#   bash scripts/devtools/smoke_filesystem_mcp.sh
set -euo pipefail

# Prefer a real node toolchain over any IDE-bundled helpers/node that may
# land first on PATH (Cursor ships its own node under
# /usr/share/cursor/resources/app/resources/helpers which breaks `npm config
# get prefix` for non-Cursor packages).
if [[ -d /home/pete/.nvm/versions/node ]]; then
  NVM_NODE_BIN="$(ls -1d /home/pete/.nvm/versions/node/*/bin 2>/dev/null | tail -1 || true)"
  if [[ -n "${NVM_NODE_BIN}" ]]; then
    PATH="${NVM_NODE_BIN}:${PATH}"
  fi
fi
PATH="${PATH//\/usr\/share\/cursor\/resources\/app\/resources\/helpers:/}"
export PATH

WORKSPACE="/home/pete/Documents/projects/Projects/News Intelligence"
ALLOWED_FILE="${WORKSPACE}/api/main.py"
DENIED_FILE="/etc/passwd"

if [[ ! -f "${ALLOWED_FILE}" ]]; then
  echo "FAIL: expected allowlisted file missing: ${ALLOWED_FILE}" >&2
  exit 2
fi

# Build a minimal MCP stdio session: initialize -> tools/call read_file allowed -> tools/call read_file denied
read -r -d '' REQUESTS <<'JSON' || true
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0.1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"__ALLOWED__"}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"__DENIED__"}}}
JSON

REQUESTS="${REQUESTS//__ALLOWED__/${ALLOWED_FILE}}"
REQUESTS="${REQUESTS//__DENIED__/${DENIED_FILE}}"

OUTPUT="$(printf '%s\n' "${REQUESTS}" | npx -y @modelcontextprotocol/server-filesystem \
  "${WORKSPACE}/api" \
  "${WORKSPACE}/scripts" \
  "${WORKSPACE}/migrations" \
  "${WORKSPACE}/lib" \
  "${WORKSPACE}/diagnostics" \
  "${WORKSPACE}/docs" \
  "${WORKSPACE}/configs" \
  "${WORKSPACE}/.continue" \
  /home/pete/Documents/projects/Projects/HomeLab-AI-Stack/docs \
  /home/pete/Documents/projects/Projects/HomeLab-AI-Stack/scripts \
  /home/pete/Documents/projects/Projects/HomeLab-AI-Stack/configs \
  2>&1 || true)"

echo "----- raw MCP output -----"
echo "${OUTPUT}" | head -40
echo "--------------------------"

# Pass conditions:
#  - id:2 has "result" with non-empty content (allowed read succeeded)
#  - id:3 has "isError":true OR "error":{ ... access ... } (denied read refused)
ALLOWED_OK="false"
DENIED_OK="false"

if echo "${OUTPUT}" | grep -E '"id":2' | grep -q '"result"'; then
  ALLOWED_OK="true"
fi
if echo "${OUTPUT}" | grep -E '"id":3' | grep -qiE '"(isError"|error").*?(access|not allowed|outside|denied)'; then
  DENIED_OK="true"
fi
# Looser fallback: any error / isError on id 3 is acceptable refusal
if [[ "${DENIED_OK}" == "false" ]] && echo "${OUTPUT}" | grep -E '"id":3' | grep -qE '"(isError":true|error":\{)'; then
  DENIED_OK="true"
fi

echo "allowed_read_succeeded=${ALLOWED_OK}"
echo "denied_read_refused=${DENIED_OK}"

if [[ "${ALLOWED_OK}" == "true" && "${DENIED_OK}" == "true" ]]; then
  echo "PASS"
  exit 0
fi
echo "FAIL" >&2
exit 1
