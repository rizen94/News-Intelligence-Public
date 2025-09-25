#!/bin/bash

# AI Session Rollback Script
# Rolls back AI session to master branch

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_status "Rolling back AI session..."

# Check if we're on an AI session branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ ! "$CURRENT_BRANCH" =~ ^ai-session- ]]; then
    print_error "You must be on an AI session branch to rollback"
    print_status "Current branch: $CURRENT_BRANCH"
    print_status "Please run: git checkout <ai-session-branch>"
    exit 1
fi

# Check if session log exists
if [ ! -f "AI_SESSION_LOG.md" ]; then
    print_error "AI session log not found"
    print_status "Please ensure you're in the correct directory"
    exit 1
fi

# Show changes that will be rolled back
print_status "Changes to be rolled back:"
git diff master --name-only
echo ""

# Show detailed changes
print_status "Detailed changes:"
git diff master --stat
echo ""

# Ask for human confirmation
print_warning "This will discard all AI session changes"
read -p "Are you sure you want to rollback this AI session? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Rollback cancelled"
    exit 0
fi

# Update session log with rollback decision
print_status "Updating session log with rollback decision..."
cat >> AI_SESSION_LOG.md << EOF

## Rollback Decision
- **Status**: ❌ REJECTED
- **Rolled back to**: master
- **Date**: $(date)
- **Human**: $(whoami)
- **Reason**: Session rejected by human

## Rollback Summary
- **Files Changed**: $(git diff master --name-only | wc -l) files
- **Lines Changed**: $(git diff master --stat | tail -1)
- **Session Branch**: $CURRENT_BRANCH
EOF

# Commit rollback decision
git add AI_SESSION_LOG.md
git commit -m "AI Session Rollback: $CURRENT_BRANCH rejected and rolled back"

# Switch to master branch
print_status "Switching to master branch..."
git checkout master

# Delete session branch
print_status "Deleting session branch..."
git branch -D "$CURRENT_BRANCH"

# Run post-rollback validation
print_status "Running post-rollback validation..."
if ! ./scripts/enforce_methodology.sh check; then
    print_warning "Post-rollback validation failed"
    print_status "Please check system status"
fi

print_success "AI session rolled back successfully!"
print_status "Session branch: $CURRENT_BRANCH (deleted)"
print_status "Rolled back to: master"
print_status "Session log: AI_SESSION_LOG.md"
print_status ""
print_status "Next steps:"
print_status "1. Review what went wrong in the session"
print_status "2. Fix any issues before starting new session"
print_status "3. Start new AI session: ./scripts/ai_session_start.sh"
print_status "4. Run: ./scripts/enforce_methodology.sh status"
