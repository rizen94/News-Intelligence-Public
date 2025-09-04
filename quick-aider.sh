#!/bin/bash

# Quick Aider Startup Script
# Assumes Ollama and aider are already installed and configured

set -e

NEWS_APP_PATH="/home/pete/Documents/Projects/News Intelligence"
OLLAMA_MODEL="deepseek-coder:33b"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Check if Ollama is running
if ! lsof -i :11434 >/dev/null 2>&1; then
    print_status "Starting Ollama..."
    ollama serve >/dev/null 2>&1 &
    sleep 3
    print_success "Ollama started"
else
    print_success "Ollama is already running"
fi

# Check if model exists
if ! ollama list | grep -q "$OLLAMA_MODEL"; then
    print_status "Pulling model: $OLLAMA_MODEL"
    ollama pull $OLLAMA_MODEL
fi

# Start aider
print_success "Starting aider with news app context..."
cd "$NEWS_APP_PATH"

# Try to find aider in common locations
AIDER_CMD="aider"
if ! command -v aider >/dev/null 2>&1; then
    if [ -f /home/pete/.local/bin/aider ]; then
        AIDER_CMD="/home/pete/.local/bin/aider"
    elif [ -f /usr/local/bin/aider ]; then
        AIDER_CMD="/usr/local/bin/aider"
    else
        print_error "aider not found. Please run the full setup script first: ./start-code-assistant.sh"
        exit 1
    fi
fi

# Start aider with core project files (reduced set to avoid token limits)
OLLAMA_API_BASE=http://localhost:11434 $AIDER_CMD --model ollama/deepseek-coder:33b --openai-api-base http://localhost:11434/v1 --openai-api-key dummy --no-gitignore --no-show-model-warnings \
  web/src/pages/Dashboard/EnhancedDashboard.js \
  web/src/pages/Articles/Articles.js \
  web/src/pages/Stories/Stories.js \
  web/src/services/newsSystemService.js \
  api/routes/articles.py \
  api/routes/stories.py \
  api/routes/dashboard.py \
  api/routes/intelligence.py \
  api/routes/search.py \
  api/routes/rag.py \
  api/routes/ml.py \
  api/main.py \
  api/app.py \
  web/src/App.js \
  api/modules/intelligence/article_processor.py \
  api/modules/ml/summarization_service.py \
  api/collectors/rss_collector.py \
  api/config/database.py \
  README.md
