#!/bin/bash

# Code Assistant Setup Script
# Starts Ollama locally with aider and news app context

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NEWS_APP_PATH="/home/pete/Documents/Projects/News Intelligence"
OLLAMA_MODEL="deepseek-coder:33b"  # More capable model
OLLAMA_PORT=11434
AIDER_PORT=8000

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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is in use
port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

# Function to install Ollama if not present
install_ollama() {
    print_status "Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
    print_success "Ollama installed successfully"
}

# Function to install aider if not present
install_aider() {
    print_status "Installing aider..."
    if command_exists pip3; then
        pip3 install aider-chat
    elif command_exists pip; then
        pip install aider-chat
    else
        print_error "Python pip not found. Please install Python and pip first."
        exit 1
    fi
    print_success "aider installed successfully"
}

# Function to start Ollama service
start_ollama() {
    # Check if Ollama is already running
    if port_in_use $OLLAMA_PORT; then
        print_success "Ollama is already running on port $OLLAMA_PORT"
    else
        print_status "Starting Ollama service..."
        # Start Ollama in background
        ollama serve >/dev/null 2>&1 &
        OLLAMA_PID=$!
        echo $OLLAMA_PID > /tmp/ollama.pid
        
        # Wait for Ollama to start
        print_status "Waiting for Ollama to start..."
        sleep 5
        
        # Check if Ollama started successfully
        if port_in_use $OLLAMA_PORT; then
            print_success "Ollama started successfully on port $OLLAMA_PORT"
        else
            print_error "Failed to start Ollama"
            exit 1
        fi
    fi
}

# Function to pull the model if not present
pull_model() {
    print_status "Checking for model: $OLLAMA_MODEL"
    
    # Check if model exists
    if ollama list | grep -q "$OLLAMA_MODEL"; then
        print_success "Model $OLLAMA_MODEL already exists"
    else
        print_status "Pulling model: $OLLAMA_MODEL (this may take a while...)"
        ollama pull $OLLAMA_MODEL
        print_success "Model $OLLAMA_MODEL pulled successfully"
    fi
}

# Function to create aider configuration
create_aider_config() {
    print_status "Creating aider configuration..."
    
    # Create .aider directory if it doesn't exist
    mkdir -p ~/.aider
    
    # Create aider config file
    cat > ~/.aider/aider.conf << EOF
# Aider Configuration for News Intelligence System
[default]
model = ollama/$OLLAMA_MODEL
openai_api_base = http://localhost:$OLLAMA_PORT/v1
openai_api_key = dummy
editor = code
auto_commits = true
auto_commits_verbose = true
pretty = true
show_diffs = true
show_parser_errors = true
voice_language = en
apply_updates = true
dirty_commits = true
dirty_staging = true
EOF
    
    print_success "Aider configuration created at ~/.aider/aider.conf"
}

# Function to create news app context file
create_context_file() {
    print_status "Creating news app context file..."
    
    # Create a comprehensive context file for the news app
    cat > "$NEWS_APP_PATH/.aider-context.md" << 'EOF'
# News Intelligence System - Code Assistant Context

## Project Overview
This is a comprehensive news intelligence system that collects, processes, and analyzes news content using AI/ML technologies.

## Key Directories and Files

### Backend API (`/api/`)
- `main.py` - Main Flask application entry point
- `app.py` - Core Flask application configuration
- `requirements.txt` - Python dependencies

### Core Modules (`/api/modules/`)
- `intelligence/` - AI-powered content analysis and processing
- `deduplication/` - Content deduplication algorithms
- `ml/` - Machine learning models and processing
- `prioritization/` - Content prioritization and ranking
- `automation/` - Automated workflow management
- `data_collection/` - RSS and content collection
- `ingestion/` - Content ingestion pipeline
- `monitoring/` - System monitoring and metrics

### Routes (`/api/routes/`)
- `articles.py` - Article management endpoints
- `intelligence.py` - Intelligence analysis endpoints
- `search.py` - Search functionality
- `stories.py` - Story tracking and management
- `rss.py` - RSS feed management
- `deduplication.py` - Deduplication management
- `automation.py` - Automation pipeline management

### Frontend (`/web/`)
- React-based web interface
- `src/components/` - Reusable UI components
- `src/pages/` - Main application pages
- `src/services/` - API service layer

### Configuration
- `docker-compose.yml` - Main Docker configuration
- `env.example` - Environment variables template
- `.env` - Environment configuration (create from env.example)

## Key Technologies
- **Backend**: Python, Flask, SQLAlchemy
- **Frontend**: React, JavaScript, CSS
- **Database**: PostgreSQL
- **AI/ML**: Custom models, RAG, summarization
- **Infrastructure**: Docker, Nginx, Redis

## Development Guidelines
1. Follow Python PEP 8 style guidelines
2. Use type hints where appropriate
3. Write comprehensive docstrings
4. Include error handling and logging
5. Test new features thoroughly
6. Update documentation when adding features

## Common Tasks
- Adding new API endpoints
- Implementing new ML models
- Creating new frontend components
- Database schema changes
- Performance optimization
- Bug fixes and debugging

## Important Notes
- The system uses a modular architecture
- AI/ML components are in `/api/modules/ml/`
- Database models are in `/api/config/database.py`
- Frontend state management uses React Context
- All API endpoints should include proper error handling
EOF
    
    print_success "Context file created at $NEWS_APP_PATH/.aider-context.md"
}

# Function to start aider with news app context
start_aider() {
    print_status "Starting aider with news app context..."
    
    # Change to news app directory
    cd "$NEWS_APP_PATH"
    
    # Find aider command
    AIDER_CMD="aider"
    if ! command -v aider >/dev/null 2>&1; then
        if [ -f /home/pete/.local/bin/aider ]; then
            AIDER_CMD="/home/pete/.local/bin/aider"
        elif [ -f /usr/local/bin/aider ]; then
            AIDER_CMD="/usr/local/bin/aider"
        else
            print_error "aider not found in PATH. Please check installation."
            exit 1
        fi
    fi
    
    # Start aider with the news app as context
    print_success "Starting aider in news app directory..."
    print_status "Use Ctrl+C to stop aider when done"
    print_status "Aider will use the news app as context for all conversations"
    
    # Start aider with core project files (reduced set to avoid token limits)
    print_status "Starting aider with core project files..."
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
}

# Function to cleanup on exit
cleanup() {
    print_status "Cleaning up..."
    
    # Kill Ollama if we started it
    if [ -f /tmp/ollama.pid ]; then
        OLLAMA_PID=$(cat /tmp/ollama.pid)
        if kill -0 $OLLAMA_PID 2>/dev/null; then
            print_status "Stopping Ollama..."
            kill $OLLAMA_PID
            rm -f /tmp/ollama.pid
        fi
    fi
    
    print_success "Cleanup complete"
}

# Set up signal handlers
trap cleanup EXIT INT TERM

# Main execution
main() {
    print_status "Starting Code Assistant Setup..."
    print_status "News App Path: $NEWS_APP_PATH"
    print_status "Ollama Model: $OLLAMA_MODEL"
    
    # Check if running from correct directory
    if [ ! -f "$NEWS_APP_PATH/api/main.py" ]; then
        print_error "Please run this script from the News Intelligence project directory"
        exit 1
    fi
    
    # Install dependencies if needed
    if ! command_exists ollama; then
        install_ollama
    else
        print_success "Ollama is already installed"
    fi
    
    if ! command_exists aider; then
        install_aider
    else
        print_success "aider is already installed"
    fi
    
    # Start Ollama
    start_ollama
    
    # Pull model
    pull_model
    
    # Create configuration
    create_aider_config
    create_context_file
    
    # Start aider
    start_aider
}

# Run main function
main "$@"
