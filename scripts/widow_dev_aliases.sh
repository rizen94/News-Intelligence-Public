#!/bin/bash
# Widow Development Environment Setup
# Add this to your ~/.bashrc or ~/.zshrc:
#   source ~/Documents/projects/News\ Intelligence/scripts/widow_dev_aliases.sh

# Configuration
export WIDOW_HOST="192.168.93.101"
export WIDOW_USER="pete"
export WIDOW_PROJECT_PATH="/home/pete/projects/News Intelligence"
export WIDOW_MOUNT_POINT="${HOME}/widow-news-intel"

# Alias: Quick SSH to Widow with automatic project navigation
alias widow-project='ssh widow "cd ~/projects/News\ Intelligence && exec bash"'

# Alias: Mount Widow project (uses the mount script)
alias widow-mount='source ~/Documents/projects/News\ Intelligence/scripts/mount_widow_project.sh mount'

# Alias: Unmount Widow project
alias widow-unmount='source ~/Documents/projects/News\ Intelligence/scripts/mount_widow_project.sh unmount'

# Alias: Check if mounted
alias widow-status='source ~/Documents/projects/News\ Intelligence/scripts/mount_widow_project.sh status'

# Alias: Quick CD to mounted project (if mounted)
widow-cd() {
    if mountpoint -q "$WIDOW_MOUNT_POINT" 2>/dev/null; then
        cd "$WIDOW_MOUNT_POINT"
    else
        echo "❌ Not mounted. Run 'widow-mount' first."
        return 1
    fi
}

# Function: Quick development session on Widow
widow-dev() {
    echo "🚀 Starting development session on Widow..."
    ssh widow "cd ~/projects/News\ Intelligence && exec bash"
}

# Function: Open VS Code Remote to Widow
widow-code() {
    echo "Opening VS Code Remote SSH to Widow..."
    code --ssh-remote=ssh://widow
}

# --- GPU handoff (PopOS local shell → Widow via SSH where noted) ---
# Bash names use hyphens; spoken form: "local GPU pause", "widow GPU resume", etc.
_HOMELAB_ROOT="${HOME}/Documents/projects/HomeLab-AI-Stack"
_NI_WIDOW_ROOT="/opt/news-intelligence"

local-gpu-pause() {
    "${_HOMELAB_ROOT}/scripts/release_popos_gpu_for_local.sh" "$@"
}

local-gpu-resume() {
    "${_HOMELAB_ROOT}/scripts/resume_popos_gpu_after_local.sh" "$@"
}

widow-gpu-pause() {
    ssh widow "${_NI_WIDOW_ROOT}/scripts/pause_for_bulk_catchup.sh" "$@"
}

widow-gpu-resume() {
    ssh widow "${_NI_WIDOW_ROOT}/scripts/resume_after_bulk_catchup.sh; sudo systemctl start news-intelligence-api-public 2>/dev/null || true"
}

# Print helpful message
echo "🔧 Widow development environment configured."
echo "   - 'widow-mount'  : Mount project via SSHFS"
echo "   - 'widow-cd'     : CD to mounted project"
echo "   - 'widow-project': SSH into project directory"
echo "   - 'widow-code'   : Open VS Code Remote to Widow"
echo "   GPU handoff (run on PopOS):"
echo "   - 'local-gpu-pause'  — pause NI/NRI + clear PopOS Ollama VRAM (local GPU pause)"
echo "   - 'local-gpu-resume' — restore NI/NRI GPU sharing (local GPU resume)"
echo "   - 'widow-gpu-pause'  — pause NI/NRI on Widow only (widow GPU pause)"
echo "   - 'widow-gpu-resume' — resume NI/NRI on Widow only (widow GPU resume)"