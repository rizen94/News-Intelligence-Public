#!/bin/bash
# Cleanup script for removing bloat: Docker, duplicate containers, and large directories

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo -e "${CYAN}🧹 Bloat Cleanup Script${NC}"
echo "=========================="
echo ""

# Function to ask for confirmation
confirm() {
    read -p "$(echo -e ${YELLOW}$1${NC} [y/N]: )" -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# 1. Docker cleanup
echo -e "${CYAN}🐳 Docker Cleanup${NC}"
echo "----------------"

# Remove stopped containers
echo "Stopped containers:"
docker ps -a --filter "status=exited" --format "  - {{.Names}} ({{.Status}})" || true
if confirm "Remove stopped containers?"; then
    docker container prune -f
    echo -e "${GREEN}✅ Stopped containers removed${NC}"
fi

# Remove duplicate/unused images
echo ""
echo "Duplicate/unused images:"
docker images --format "{{.Repository}}:{{.Tag}}" | sort | uniq -d | while read img; do
    echo "  - $img (duplicate)"
done
docker images --filter "dangling=true" --format "  - {{.Repository}}:{{.Tag}} (dangling)" || true

if confirm "Remove duplicate and unused images?"; then
    # Remove dangling images
    docker image prune -f
    # Show old images for manual selection
    echo ""
    echo "Old images (older than 1 month):"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" | head -15
    echo ""
    if confirm "Remove all unused images (not just dangling)?"; then
        docker image prune -a -f
        echo -e "${GREEN}✅ Unused images removed${NC}"
    fi
fi

# Clean build cache
echo ""
BUILD_CACHE_SIZE=$(docker system df | grep "Build Cache" | awk '{print $4}')
echo "Build cache size: $BUILD_CACHE_SIZE"
if confirm "Clean Docker build cache?"; then
    docker builder prune -f
    echo -e "${GREEN}✅ Build cache cleaned${NC}"
fi

# 2. Large directories
echo ""
echo -e "${CYAN}💾 Large Directory Cleanup${NC}"
echo "-------------------------"

# .venv
if [ -d ".venv" ]; then
    VENV_SIZE=$(du -sh .venv 2>/dev/null | awk '{print $1}')
    echo ".venv: $VENV_SIZE"
    if confirm "Remove .venv? (can recreate with: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt)"; then
        rm -rf .venv
        echo -e "${GREEN}✅ .venv removed${NC}"
    fi
fi

# node_modules
if [ -d "web/node_modules" ]; then
    NODE_SIZE=$(du -sh web/node_modules 2>/dev/null | awk '{print $1}')
    echo "web/node_modules: $NODE_SIZE"
    if confirm "Remove node_modules? (can reinstall with: cd web && npm install)"; then
        rm -rf web/node_modules
        echo -e "${GREEN}✅ node_modules removed${NC}"
    fi
fi

# ollama_data (move to NAS)
if [ -d "ollama_data" ]; then
    OLLAMA_SIZE=$(du -sh ollama_data 2>/dev/null | awk '{print $1}')
    echo "ollama_data: $OLLAMA_SIZE"
    if confirm "Move ollama_data to NAS?"; then
        if mountpoint -q /mnt/nas 2>/dev/null; then
            NAS_OLLAMA="/mnt/nas/news-intelligence/ollama_data"
            mkdir -p "$NAS_OLLAMA"
            echo "Moving to $NAS_OLLAMA..."
            mv ollama_data/* "$NAS_OLLAMA/" 2>/dev/null || true
            rmdir ollama_data 2>/dev/null || true
            ln -s "$NAS_OLLAMA" ollama_data
            echo -e "${GREEN}✅ ollama_data moved to NAS${NC}"
        else
            echo -e "${RED}❌ NAS not mounted${NC}"
        fi
    fi
fi

# 3. Log rotation
echo ""
echo -e "${CYAN}📋 Log Cleanup${NC}"
echo "--------------"
LOG_SIZE=$(find . -type f \( -name "*.log" -o -name "*.log.*" \) -exec du -ch {} + 2>/dev/null | tail -1 | awk '{print $1}')
echo "Total log size: $LOG_SIZE"
if confirm "Rotate/compress old logs (>1MB)?"; then
    find . -type f -name "*.log" -size +1M -exec gzip {} \; 2>/dev/null || true
    echo -e "${GREEN}✅ Logs compressed${NC}"
fi

# 4. Python cache
echo ""
echo -e "${CYAN}🗂️  Cache Cleanup${NC}"
echo "----------------"
PYCACHE_COUNT=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
echo "__pycache__ directories: $PYCACHE_COUNT"
if confirm "Remove __pycache__ directories?"; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    echo -e "${GREEN}✅ Python cache cleaned${NC}"
fi

# Summary
echo ""
echo -e "${CYAN}📊 Cleanup Summary${NC}"
echo "=================="
echo ""
echo "Docker disk usage:"
docker system df 2>/dev/null || echo "  Docker not accessible"
echo ""
echo "Project size:"
du -sh . 2>/dev/null | awk '{print "  " $1}'
echo ""
echo "Available disk space:"
df -h . | tail -1 | awk '{print "  " $4 " available (" $5 " used)"}'
echo ""
echo -e "${GREEN}✅ Cleanup complete!${NC}"

