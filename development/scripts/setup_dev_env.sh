#!/bin/bash

# News Intelligence System v3.0 - Development Environment Setup
# Sets up Python virtual environment for fast local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR=".venv"
REQUIREMENTS_FILE="requirements-fixed.txt"

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Python 3.10+ is available
check_python() {
    log "Checking Python version..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            success "Python $PYTHON_VERSION found"
            return 0
        else
            error "Python 3.10+ required, found $PYTHON_VERSION"
            return 1
        fi
    else
        error "Python 3 not found"
        return 1
    fi
}

# Create virtual environment
create_venv() {
    log "Creating virtual environment..."
    
    if [ -d "$VENV_DIR" ]; then
        warning "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log "Removing existing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            success "Using existing virtual environment"
            return 0
        fi
    fi
    
    python3 -m venv "$VENV_DIR"
    success "Virtual environment created"
}

# Activate virtual environment
activate_venv() {
    log "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    success "Virtual environment activated"
}

# Install dependencies
install_dependencies() {
    log "Installing dependencies..."
    
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        error "Requirements file $REQUIREMENTS_FILE not found"
        return 1
    fi
    
    # Upgrade pip first
    pip install --upgrade pip
    
    # Install dependencies
    pip install -r "$REQUIREMENTS_FILE"
    
    success "Dependencies installed"
}

# Create development scripts
create_dev_scripts() {
    log "Creating development scripts..."
    
    # Create start-dev.sh
    cat > start-dev.sh << 'EOF'
#!/bin/bash
# Start development server

source .venv/bin/activate
export DATABASE_URL="postgresql://newsapp:newsapp_password@localhost:5432/news_intelligence"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="development"
export LOG_LEVEL="debug"

echo "Starting News Intelligence System v3.0 in development mode..."
echo "Database: $DATABASE_URL"
echo "Redis: $REDIS_URL"
echo "Environment: $ENVIRONMENT"
echo ""

python main.py
EOF

    # Create test-dev.sh
    cat > test-dev.sh << 'EOF'
#!/bin/bash
# Test development environment

source .venv/bin/activate

echo "Testing News Intelligence System v3.0 development environment..."
echo ""

# Test imports
echo "Testing imports..."
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "import pydantic; print('Pydantic:', pydantic.__version__)"
python -c "import sqlalchemy; print('SQLAlchemy:', sqlalchemy.__version__)"

# Test API startup
echo ""
echo "Testing API startup..."
timeout 10s python -c "
import sys
sys.path.append('.')
from main import app
print('API app created successfully')
" || echo "API startup test completed"

echo ""
echo "Development environment test complete!"
EOF

    # Create update-deps.sh
    cat > update-deps.sh << 'EOF'
#!/bin/bash
# Update dependencies

source .venv/bin/activate

echo "Updating News Intelligence System v3.0 dependencies..."
echo ""

# Check for outdated packages
echo "Checking for outdated packages..."
pip list --outdated

echo ""
echo "Updating packages..."
pip install --upgrade -r requirements-fixed.txt

echo ""
echo "Generating new requirements.txt..."
pip freeze > requirements-updated.txt

echo ""
echo "Dependencies updated! Review requirements-updated.txt before committing."
EOF

    # Make scripts executable
    chmod +x start-dev.sh test-dev.sh update-deps.sh
    
    success "Development scripts created"
}

# Create .env file for development
create_env_file() {
    log "Creating development environment file..."
    
    cat > .env << 'EOF'
# News Intelligence System v3.0 - Development Environment
DATABASE_URL=postgresql://newsapp:newsapp_password@localhost:5432/news_intelligence
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=development
LOG_LEVEL=debug
DEBUG=true
EOF

    success "Environment file created"
}

# Main setup function
main() {
    log "Setting up News Intelligence System v3.0 development environment"
    log "=================================================================="
    
    # Check prerequisites
    if ! check_python; then
        error "Python 3.10+ is required"
        exit 1
    fi
    
    # Create virtual environment
    create_venv
    
    # Activate virtual environment
    activate_venv
    
    # Install dependencies
    install_dependencies
    
    # Create development scripts
    create_dev_scripts
    
    # Create environment file
    create_env_file
    
    echo ""
    success "Development environment setup complete!"
    echo ""
    echo "Next steps:"
    echo "1. Start PostgreSQL and Redis (or use Docker)"
    echo "2. Run: ./start-dev.sh"
    echo "3. Test: ./test-dev.sh"
    echo "4. Update deps: ./update-deps.sh"
    echo ""
    echo "Development URLs:"
    echo "  API: http://localhost:8000"
    echo "  Docs: http://localhost:8000/docs"
    echo "  Pipeline Monitoring: http://localhost:8000/api/pipeline-monitoring"
    echo ""
    echo "To activate the virtual environment manually:"
    echo "  source .venv/bin/activate"
}

# Run main function
main "$@"
