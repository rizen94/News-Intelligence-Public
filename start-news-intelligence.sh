#!/usr/bin/env bash
# Wrapper so News Intelligence can be started from anywhere.
# Install: ln -sf "$(pwd)/start-news-intelligence.sh" ~/bin/start-news-intelligence
# Ensure ~/bin is in your PATH (add to ~/.bashrc: export PATH="$HOME/bin:$PATH")

# Resolve real path (follow symlinks) so it works when run from ~/bin
SCRIPT_PATH="${BASH_SOURCE[0]}"
[[ -L "$SCRIPT_PATH" ]] && SCRIPT_PATH="$(readlink -f "$SCRIPT_PATH")"
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"

exec "$PROJECT_ROOT/start_system.sh" "$@"
