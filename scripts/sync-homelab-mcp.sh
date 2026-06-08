#!/usr/bin/env bash
# Sync HomeLab MCP stack into Cursor, Cline, code-server, and Continue (News Intelligence).
set -euo pipefail
HOMELAB="${HOMELAB_ROOT:-/home/pete/Documents/projects/HomeLab-AI-Stack}"
exec "$HOMELAB/scripts/sync-agent-mcp.sh"
