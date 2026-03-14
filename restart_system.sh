#!/bin/bash

# News Intelligence System v5.0 - Restart Script
# Stops API and Frontend, then starts them again (same as stop + start).
# Use this after changing .env (e.g. NEWS_API_KEY) so the API picks up new variables.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping services..."
bash "$SCRIPT_DIR/stop_system.sh"

echo ""
echo "Waiting 3 seconds before starting..."
sleep 3

echo ""
echo "Starting services..."
bash "$SCRIPT_DIR/start_system.sh"
