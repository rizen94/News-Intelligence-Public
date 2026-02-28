#!/usr/bin/env bash
# Run finance unit tests using project venv.
# From project root: ./scripts/run_finance_tests.sh
# Uses uv run when available so venv deps are used.

set -e
cd "$(dirname "$0")/.."

if command -v uv &>/dev/null; then
    uv run pytest tests/unit/test_finance_*.py -v --tb=short
else
    python -m pytest tests/unit/test_finance_*.py -v --tb=short
fi
