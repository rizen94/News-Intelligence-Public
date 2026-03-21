#!/bin/bash
# Cleanup script for home directory bloat

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🧹 Home Directory Bloat Cleanup${NC}"
echo "=================================="
echo ""

# Function to ask for confirmation
confirm() {
    read -p "$(echo -e ${YELLOW}$1${NC} [y/N]: )" -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# 1. Empty Trash (316GB!)
TRASH_SIZE=$(du -sh ~/.local/share/Trash 2>/dev/null | awk '{print $1}')
echo -e "${RED}🗑️  TRASH: $TRASH_SIZE${NC}"
echo "This is 35% of your entire disk!"
if confirm "Empty trash? (This will permanently delete 316GB)"; then
    rm -rf ~/.local/share/Trash/*
    echo -e "${GREEN}✅ Trash emptied${NC}"
else
    echo "Skipped"
fi

# 2. Steam cleanup
echo ""
STEAM_SIZE=$(du -sh ~/.local/share/Steam 2>/dev/null | awk '{print $1}')
echo -e "${YELLOW}🎮 Steam: $STEAM_SIZE${NC}"
if confirm "Clean Steam download cache? (keeps games, removes cache)"; then
    rm -rf ~/.local/share/Steam/appcache
    rm -rf ~/.local/share/Steam/htmlcache
    echo -e "${GREEN}✅ Steam cache cleaned${NC}"
fi

# 3. Ollama models
echo ""
OLLAMA_SIZE=$(du -sh ~/.ollama/models 2>/dev/null | awk '{print $1}')
echo -e "${YELLOW}🤖 Ollama models: $OLLAMA_SIZE${NC}"
echo "Models in ~/.ollama/models:"
ls -lh ~/.ollama/models 2>/dev/null | head -10 || echo "  No models found"
if confirm "Move Ollama models to NAS? (requires NAS mount)"; then
    if mountpoint -q /mnt/nas 2>/dev/null; then
        NAS_OLLAMA="/mnt/nas/news-intelligence/ollama_models"
        mkdir -p "$NAS_OLLAMA"
        echo "Moving models to $NAS_OLLAMA..."
        mv ~/.ollama/models/* "$NAS_OLLAMA/" 2>/dev/null || true
        ln -s "$NAS_OLLAMA" ~/.ollama/models
        echo -e "${GREEN}✅ Ollama models moved to NAS${NC}"
    else
        echo -e "${RED}❌ NAS not mounted${NC}"
    fi
fi

# 4. Cache cleanup
echo ""
CACHE_SIZE=$(du -sh ~/.cache 2>/dev/null | awk '{print $1}')
echo -e "${YELLOW}🗂️  Cache: $CACHE_SIZE${NC}"
if confirm "Clean user cache? (safe, can be regenerated)"; then
    rm -rf ~/.cache/*
    echo -e "${GREEN}✅ Cache cleaned${NC}"
fi

# 5. Flatpak cleanup
echo ""
FLATPAK_SIZE=$(du -sh ~/.var 2>/dev/null | awk '{print $1}')
echo -e "${YELLOW}📦 Flatpak: $FLATPAK_SIZE${NC}"
if confirm "Clean Flatpak cache? (flatpak uninstall --unused)"; then
    flatpak uninstall --unused -y 2>/dev/null || echo "  Flatpak not available or no unused packages"
    echo -e "${GREEN}✅ Flatpak cleanup attempted${NC}"
fi

# Summary
echo ""
echo -e "${CYAN}📊 Cleanup Summary${NC}"
echo "=================="
echo ""
echo "Disk space:"
df -h / | tail -1 | awk '{print "  Available: " $4 " (" $5 " used)"}'
echo ""
echo "Home directory:"
du -sh ~ 2>/dev/null | awk '{print "  " $1}'
echo ""
echo -e "${GREEN}✅ Cleanup complete!${NC}"

