#!/bin/bash
# Wrapper script for daily batch processor
# Ensures proper environment and error handling

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/api:$PWD:$PYTHONPATH"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the batch processor
python3 api/scripts/daily_batch_processor.py

# Exit with the script's exit code
exit $?

