#!/bin/bash

# Quick Docker Cleanup - Manual Run
# Use this for immediate cleanup without waiting for the scheduled timer

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                QUICK DOCKER CLEANUP                         ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
}

print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Show current usage
echo -e "${YELLOW}Current Docker resource usage:${NC}"
docker system df

echo ""
print_warning "This will remove:"
echo "  • Stopped containers"
echo "  • Unused images (older than 24h)"
echo "  • Unused volumes"
echo "  • Unused networks"
echo "  • Build cache"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_warning "Cleanup cancelled"
    exit 0
fi

# Run cleanup
print_status "Starting cleanup..."

# Remove stopped containers
print_status "Removing stopped containers..."
docker container prune -f

# Remove unused images
print_status "Removing unused images..."
docker image prune -a --filter "until=24h" -f

# Remove unused volumes
print_status "Removing unused volumes..."
docker volume prune -f

# Remove unused networks
print_status "Removing unused networks..."
docker network prune -f

# Remove build cache
print_status "Removing build cache..."
docker builder prune -f

# Show final usage
echo ""
print_status "Cleanup completed!"
echo -e "${YELLOW}Final Docker resource usage:${NC}"
docker system df

# Show memory usage
echo ""
echo -e "${YELLOW}System memory usage:${NC}"
free -h




