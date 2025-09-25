#!/bin/bash

# AI Session End Script
# Validates AI session and prepares for human approval

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

print_status "Ending AI development session..."

# Check if we're on an AI session branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ ! "$CURRENT_BRANCH" =~ ^ai-session- ]]; then
    print_error "You must be on an AI session branch to end a session"
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

# Run comprehensive validation
print_status "Running comprehensive validation..."
if ! ./scripts/enforce_methodology.sh check; then
    print_error "System validation failed"
    print_status "Please fix issues before ending session"
    exit 1
fi

# Test pipeline functionality
print_status "Testing pipeline functionality..."
if ! ./scripts/test_pipeline.sh; then
    print_warning "Pipeline tests failed"
    print_status "Please review and fix issues"
fi

# Check API health
print_status "Checking API health..."
if curl -s "http://localhost:8000/api/health/" | jq -e '.success' >/dev/null 2>&1; then
    print_success "API is healthy"
else
    print_error "API health check failed"
    print_status "Please check API container logs"
fi

# Check frontend accessibility
print_status "Checking frontend accessibility..."
if curl -s "http://localhost:80" | grep -q "News Intelligence System"; then
    print_success "Frontend is accessible"
else
    print_error "Frontend is not accessible"
    print_status "Please check frontend container logs"
fi

# Show changes made
print_status "Changes made in this session:"
git diff master --name-only

# Show detailed changes
print_status "Detailed changes:"
git diff master --stat

# Update session log with validation results
print_status "Updating session log with validation results..."
cat >> AI_SESSION_LOG.md << EOF

## Validation Results
- **System Checks**: $(./scripts/enforce_methodology.sh check >/dev/null 2>&1 && echo "✅ Passed" || echo "❌ Failed")
- **API Health**: $(curl -s "http://localhost:8000/api/health/" | jq -e '.success' >/dev/null 2>&1 && echo "✅ Healthy" || echo "❌ Unhealthy")
- **Frontend Access**: $(curl -s "http://localhost:80" | grep -q "News Intelligence System" && echo "✅ Accessible" || echo "❌ Not Accessible")
- **Files Changed**: $(git diff master --name-only | wc -l) files
- **Lines Changed**: $(git diff master --stat | tail -1)

## Next Steps
1. **Human Review**: Review all changes with `git diff master`
2. **Manual Testing**: Test functionality manually
3. **Decision**: Choose to promote or rollback
4. **Promote**: Run `./scripts/ai_session_promote.sh`
5. **Rollback**: Run `./scripts/ai_session_rollback.sh`
EOF

# Commit validation results
git add AI_SESSION_LOG.md
git commit -m "AI Session End: Validation completed"

print_success "AI session ended successfully!"
print_status "Session branch: $CURRENT_BRANCH"
print_status "Session log: AI_SESSION_LOG.md"
print_status ""
print_status "Next steps:"
print_status "1. Review changes: git diff master"
print_status "2. Test functionality manually"
print_status "3. Decide: Promote or Rollback"
print_status "4. Promote: ./scripts/ai_session_promote.sh"
print_status "5. Rollback: ./scripts/ai_session_rollback.sh"
