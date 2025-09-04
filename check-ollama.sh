#!/bin/bash

# Quick Ollama Status Check
# No more TCP bind errors!

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Ollama is running
if lsof -i :11434 >/dev/null 2>&1; then
    print_success "Ollama is running on port 11434"
    
    # Check available models
    print_status "Available models:"
    ollama list
    
    # Test API
    print_status "Testing API connection..."
    if curl -s http://localhost:11434/api/tags >/dev/null; then
        print_success "API is responding"
    else
        print_error "API is not responding"
    fi
else
    print_error "Ollama is not running"
    print_status "Start it with: ollama serve"
fi
