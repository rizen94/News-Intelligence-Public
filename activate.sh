#!/bin/bash
# Activate the News Intelligence virtual environment
# Source this file: source activate.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VIRTUAL_ENV="$SCRIPT_DIR/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"

# CUDA paths (if toolkit is installed)
if [ -d /usr/local/cuda ]; then
    export CUDA_HOME=/usr/local/cuda
    export PATH="$CUDA_HOME/bin:$PATH"
    export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
fi

# Verify GPU is accessible (if torch installed)
python -c "
try:
    import torch
    if torch.cuda.is_available():
        print(f'GPU: {torch.cuda.get_device_name(0)} — {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB VRAM')
    else:
        print('GPU: Not available (torch installed without CUDA)')
except ImportError:
    pass
" 2>/dev/null

echo "Environment activated: news-intelligence"
echo "Python: $(python --version 2>/dev/null)"
