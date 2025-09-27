#!/bin/bash

# AI Session Start Script
# Creates a new AI development session with proper validation

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

# Check if session description is provided
if [ $# -eq 0 ]; then
    print_error "Please provide a session description"
    echo "Usage: $0 \"Session description\""
    echo "Example: $0 \"Feature: Add new dashboard component\""
    exit 1
fi

SESSION_DESCRIPTION="$1"
SESSION_BRANCH="ai-session-$(date +%Y%m%d-%H%M%S)"
SESSION_LOG="AI_SESSION_LOG.md"

print_status "Starting AI development session..."
print_status "Session: $SESSION_DESCRIPTION"
print_status "Branch: $SESSION_BRANCH"

# Check if we're on master branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "master" ]; then
    print_error "You must be on master branch to start an AI session"
    print_status "Current branch: $CURRENT_BRANCH"
    print_status "Please run: git checkout master"
    exit 1
fi

# Check if working directory is clean
if ! git diff-index --quiet HEAD --; then
    print_error "Working directory is not clean"
    print_status "Please commit or stash your changes first"
    git status --short
    exit 1
fi

# Check system status
print_status "Checking system status..."
if ! ./scripts/enforce_methodology.sh check >/dev/null 2>&1; then
    print_error "System checks failed"
    print_status "Please fix system issues before starting AI session"
    exit 1
fi

# Create session branch
print_status "Creating session branch: $SESSION_BRANCH"
git checkout -b "$SESSION_BRANCH"

# Create session log
print_status "Creating session log..."
cat > "$SESSION_LOG" << EOF
# AI Development Session

## Session Information
- **Date**: $(date)
- **Branch**: $SESSION_BRANCH
- **Human**: $(whoami)
- **AI Assistant**: [AI system used]

## Session Intent
$SESSION_DESCRIPTION

## Changes Made
[To be filled by AI during session]

## AI Reasoning
[To be filled by AI during session]

## Human Validation
- [ ] All changes reviewed by human
- [ ] All functionality tested manually
- [ ] No breaking changes detected
- [ ] Documentation updated appropriately

## Promotion Decision
- [ ] Approved for promotion to master
- [ ] Rejected - rollback required
- [ ] Requires additional changes

## Notes
[Any additional notes or concerns]
EOF

# Commit session start
git add "$SESSION_LOG"
git commit -m "AI Session Start: $SESSION_DESCRIPTION"

print_success "AI session started successfully!"
print_status "Session branch: $SESSION_BRANCH"
print_status "Session log: $SESSION_LOG"
print_status "Ready for AI development work"
print_status ""
print_status "Next steps:"
print_status "1. AI makes changes across multiple files"
print_status "2. Human reviews changes in real-time"
print_status "3. AI explains reasoning for each change"
print_status "4. Human validates each change before proceeding"
print_status "5. Run: ./scripts/ai_session_end.sh when session is complete"
