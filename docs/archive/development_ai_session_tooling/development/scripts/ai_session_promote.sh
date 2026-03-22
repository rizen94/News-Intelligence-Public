#!/bin/bash

# AI Session Promote Script
# Promotes AI session to master branch after human approval

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

print_status "Promoting AI session to master..."

# Check if we're on an AI session branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ ! "$CURRENT_BRANCH" =~ ^ai-session- ]]; then
    print_error "You must be on an AI session branch to promote"
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

# Show changes that will be promoted
print_status "Changes to be promoted:"
git diff master --name-only
echo ""

# Show detailed changes
print_status "Detailed changes:"
git diff master --stat
echo ""

# Ask for human confirmation
print_warning "This will merge all AI session changes into master branch"
read -p "Are you sure you want to promote this AI session? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Promotion cancelled"
    exit 0
fi

# Run final validation
print_status "Running final validation..."
if ! ./scripts/production/enforce_methodology.sh check; then
    print_error "Final validation failed"
    print_status "Please fix issues before promoting"
    exit 1
fi

# Switch to master branch
print_status "Switching to master branch..."
git checkout master

# Merge AI session branch
print_status "Merging AI session branch..."
git merge "$CURRENT_BRANCH" --no-ff -m "AI Session: $CURRENT_BRANCH

$(git log --oneline $CURRENT_BRANCH | head -5)"

# Update session log with promotion
print_status "Updating session log with promotion decision..."
cat >> AI_SESSION_LOG.md << EOF

## Promotion Decision
- **Status**: ✅ APPROVED
- **Promoted to**: master
- **Date**: $(date)
- **Human**: $(whoami)
- **Final Validation**: ✅ Passed

## Promotion Summary
- **Files Changed**: $(git diff HEAD~1 --name-only | wc -l) files
- **Lines Changed**: $(git diff HEAD~1 --stat | tail -1)
- **Session Branch**: $CURRENT_BRANCH
EOF

# Commit promotion decision
git add AI_SESSION_LOG.md
git commit -m "AI Session Promotion: $CURRENT_BRANCH approved and merged"

# Clean up session branch
print_status "Cleaning up session branch..."
git branch -d "$CURRENT_BRANCH"

# Run post-promotion validation
print_status "Running post-promotion validation..."
if ! ./scripts/production/enforce_methodology.sh check; then
    print_warning "Post-promotion validation failed"
    print_status "Please check system status"
fi

print_success "AI session promoted successfully!"
print_status "Session branch: $CURRENT_BRANCH"
print_status "Merged into: master"
print_status "Session log: AI_SESSION_LOG.md"
print_status ""
print_status "Next steps:"
print_status "1. Test functionality manually"
print_status "2. Monitor system for any issues"
print_status "3. Consider promoting to production if stable"
print_status "4. Run: ./scripts/production/enforce_methodology.sh promote (to production)"
