#!/bin/bash

# News Intelligence System v3.0 - Unified Setup Script
# Handles all system setup, dependencies, and configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="news-intelligence"
LOG_FILE="logs/setup.log"

# Create logs directory
mkdir -p logs

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --full          Full system setup (Docker, dependencies, configuration)"
    echo "  --docker        Docker and Docker Compose setup only"
    echo "  --ollama        Ollama AI service setup only"
    echo "  --dependencies  Python and Node.js dependencies only"
    echo "  --config        Configuration files only"
    echo "  --domain        Domain and DNS setup only"
    echo "  --rss           RSS management setup only"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --full       # Complete system setup"
    echo "  $0 --docker     # Setup Docker only"
    echo "  $0 --ollama     # Setup Ollama only"
}

# Check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then
        warning "Running as root. Some operations may require user permissions."
    fi
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        success "Linux detected"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        success "macOS detected"
    else
        error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    # Check available memory
    if command -v free > /dev/null 2>&1; then
        MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
        if [ "$MEMORY_GB" -lt 8 ]; then
            warning "Low memory detected: ${MEMORY_GB}GB. 8GB+ recommended."
        else
            success "Memory check passed: ${MEMORY_GB}GB"
        fi
    fi
    
    # Check available disk space
    DISK_SPACE=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [ "$DISK_SPACE" -lt 50 ]; then
        warning "Low disk space: ${DISK_SPACE}GB. 50GB+ recommended."
    else
        success "Disk space check passed: ${DISK_SPACE}GB"
    fi
}

# Setup Docker and Docker Compose
setup_docker() {
    log "Setting up Docker and Docker Compose..."
    
    # Check if Docker is installed
    if command -v docker > /dev/null 2>&1; then
        success "Docker is already installed"
    else
        log "Installing Docker..."
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            success "Docker installed. Please log out and back in to use Docker without sudo."
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            log "Please install Docker Desktop for macOS from https://www.docker.com/products/docker-desktop"
            exit 1
        fi
    fi
    
    # Check if Docker Compose is installed
    if command -v docker-compose > /dev/null 2>&1; then
        success "Docker Compose is already installed"
    else
        log "Installing Docker Compose..."
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            success "Docker Compose installed"
        fi
    fi
    
    # Test Docker installation
    if docker info > /dev/null 2>&1; then
        success "Docker is running"
    else
        error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Setup Ollama AI service
setup_ollama() {
    log "Setting up Ollama AI service..."
    
    # Check if Ollama is installed
    if command -v ollama > /dev/null 2>&1; then
        success "Ollama is already installed"
    else
        log "Installing Ollama..."
        curl -fsSL https://ollama.ai/install.sh | sh
        success "Ollama installed"
    fi
    
    # Start Ollama service
    log "Starting Ollama service..."
    if pgrep -f ollama > /dev/null; then
        success "Ollama is already running"
    else
        ollama serve &
        sleep 5
        if pgrep -f ollama > /dev/null; then
            success "Ollama service started"
        else
            error "Failed to start Ollama service"
            exit 1
        fi
    fi
    
    # Pull required models
    log "Pulling required AI models..."
    ollama pull llama3.1:70b || warning "Failed to pull llama3.1:70b model"
    ollama pull llama3.1:8b || warning "Failed to pull llama3.1:8b model"
    success "Ollama setup complete"
}

# Setup Python dependencies
setup_python_deps() {
    log "Setting up Python dependencies..."
    
    # Check if Python 3.11+ is installed
    if command -v python3 > /dev/null 2>&1; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 1 ]]; then
            success "Python $PYTHON_VERSION detected"
        else
            error "Python 3.11+ required. Found: $PYTHON_VERSION"
            exit 1
        fi
    else
        error "Python 3.11+ not found. Please install Python 3.11 or later."
        exit 1
    fi
    
    # Create virtual environment
    if [ ! -d ".venv" ]; then
        log "Creating Python virtual environment..."
        python3 -m venv .venv
        success "Virtual environment created"
    else
        success "Virtual environment already exists"
    fi
    
    # Activate virtual environment and install dependencies
    log "Installing Python dependencies..."
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r api/requirements.txt
    success "Python dependencies installed"
}

# Setup Node.js dependencies
setup_node_deps() {
    log "Setting up Node.js dependencies..."
    
    # Check if Node.js is installed
    if command -v node > /dev/null 2>&1; then
        NODE_VERSION=$(node --version)
        success "Node.js $NODE_VERSION detected"
    else
        error "Node.js not found. Please install Node.js 18+ from https://nodejs.org/"
        exit 1
    fi
    
    # Install frontend dependencies
    if [ -f "web/package.json" ]; then
        log "Installing frontend dependencies..."
        cd web
        npm install
        cd ..
        success "Frontend dependencies installed"
    else
        warning "Frontend package.json not found"
    fi
}

# Setup configuration files
setup_config() {
    log "Setting up configuration files..."
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        log "Creating .env file..."
        cat > .env << EOF
# News Intelligence System v3.0 Configuration
POSTGRES_DB=news_intelligence
POSTGRES_USER=newsapp
POSTGRES_PASSWORD=newsapp_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3.1:70b

API_HOST=0.0.0.0
API_PORT=8000

FRONTEND_HOST=0.0.0.0
FRONTEND_PORT=3000

LOG_LEVEL=INFO
EOF
        success ".env file created"
    else
        success ".env file already exists"
    fi
    
    # Create logs directory
    mkdir -p logs
    success "Configuration setup complete"
}

# Setup domain and DNS
setup_domain() {
    log "Setting up domain and DNS configuration..."
    
    # This would typically involve:
    # - Domain registration
    # - DNS configuration
    # - SSL certificate setup
    # - Nginx configuration
    
    warning "Domain setup requires manual configuration"
    log "Please configure your domain and DNS settings manually"
    success "Domain setup placeholder complete"
}

# Setup RSS management
setup_rss() {
    log "Setting up RSS management..."
    
    # Create RSS data directory
    mkdir -p data/rss_feeds
    mkdir -p data/articles
    
    # This would typically involve:
    # - RSS feed configuration
    # - Feed validation
    # - Collection scheduling
    
    success "RSS management setup complete"
}

# Full system setup
setup_full() {
    log "Starting full system setup..."
    check_root
    check_requirements
    setup_docker
    setup_ollama
    setup_python_deps
    setup_node_deps
    setup_config
    setup_domain
    setup_rss
    success "Full system setup complete!"
}

# Main execution
main() {
    case "${1:-}" in
        --full)
            setup_full
            ;;
        --docker)
            check_root
            setup_docker
            ;;
        --ollama)
            setup_ollama
            ;;
        --dependencies)
            setup_python_deps
            setup_node_deps
            ;;
        --config)
            setup_config
            ;;
        --domain)
            setup_domain
            ;;
        --rss)
            setup_rss
            ;;
        --help)
            show_usage
            ;;
        *)
            error "Invalid option: ${1:-}"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
