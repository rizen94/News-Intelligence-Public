#!/usr/bin/env bash
# Wrapper so News Intelligence can be started from anywhere (e.g. terminal shortcut in ~/bin).
# Install: ln -sf "/path/to/News Intelligence/start-news-intelligence.sh" ~/bin/start-news-intelligence

set -e
# Resolve real path (follow symlinks) so it works when run from ~/bin or a .desktop launcher
SCRIPT_PATH="${BASH_SOURCE[0]}"
[[ -L "$SCRIPT_PATH" ]] && SCRIPT_PATH="$(readlink -f "$SCRIPT_PATH")"
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

# Ensure we run start_system.sh from project root so it finds .env and paths
cd "$PROJECT_ROOT"
exec bash "$PROJECT_ROOT/start_system.sh" "$@"
