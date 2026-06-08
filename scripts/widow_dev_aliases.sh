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

# Print helpful message
echo "🔧 Widow development environment configured."
echo "   - 'widow-mount'  : Mount project via SSHFS"
echo "   - 'widow-cd'     : CD to mounted project"
echo "   - 'widow-project': SSH into project directory"
echo "   - 'widow-code'   : Open VS Code Remote to Widow"