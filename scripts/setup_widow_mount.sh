#!/bin/bash
# Setup script for Widow development environment
# Installs SSHFS, sets up mount point, and configures aliases

set -e

echo "========================================="
echo "Widow Development Environment Setup"
echo "========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if SSHFS is installed
echo -n "${YELLOW}Checking for SSHFS... ${NC}"
if ! command -v sshfs &> /dev/null; then
    echo "${RED}Not found${NC}"
    echo "${YELLOW}Installing SSHFS...${NC}"
    sudo apt-get update -qq
    sudo apt-get install -y -qq sshfs
    echo "${GREEN}✅ SSHFS installed${NC}"
else
    echo "${GREEN}Already installed${NC}"
fi

# Make scripts executable
echo ""
echo -n "${YELLOW}Making scripts executable... ${NC}"
chmod +x scripts/mount_widow_project.sh
chmod +x scripts/widow_dev_aliases.sh
echo "${GREEN}✅ Done${NC}"

# Create mount point directory
echo ""
echo -n "${YELLOW}Creating mount point directory... ${NC}"
mkdir -p "$HOME/widow-news-intel"
echo "${GREEN}✅ ~/widow-news-intel created${NC}"

# Ask user if they want to add aliases to .bashrc
echo ""
echo -n "${YELLOW}Would you like to add quick access aliases to ~/.bashrc? (y/n) ${NC}"
read -r answer
if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
    echo "${YELLOW}Adding aliases to ~/.bashrc...${NC}"
    
    # Check if already added
    if ! grep -q "widow_dev_aliases.sh" ~/.bashrc 2>/dev/null; then
        echo "" >> ~/.bashrc
        echo "# Widow Development Environment - Added $(date)" >> ~/.bashrc
        echo "source ~/Documents/projects/News\ Intelligence/scripts/widow_dev_aliases.sh" >> ~/.bashrc
        echo "${GREEN}✅ Aliases added to ~/.bashrc${NC}"
        echo "${GREEN}   Run 'source ~/.bashrc' to activate them now${NC}"
    else
        echo "${GREEN}✅ Aliases already in ~/.bashrc${NC}"
    fi
fi

# Verify SSH connection to Widow
echo ""
echo -n "${YELLOW}Verifying SSH connection to Widow... ${NC}"
if ssh -o ConnectTimeout=5 -o BatchMode=yes widow "echo Connected" &>/dev/null; then
    echo "${GREEN}✅ Connected${NC}"
else
    echo "${RED}❌ Cannot connect to Widow via SSH${NC}"
    echo "   Please ensure:"
    echo "   - Widow server is on (192.168.93.101)"
    echo "   - SSH is running on Widow"
    echo "   - 'widow' is in your SSH known_hosts or configured"
fi

# Test if SSHFS can see the project directory
echo ""
echo -n "${YELLOW}Testing SSHFS visibility of project directory... ${NC}"
if sshfs -o allow_other,defer_permission_checks -o auto_unmount \
       "pete@192.168.93.101:/home/pete/projects/News\ Intelligence" \
       "$HOME/widow-news-intel" &>/dev/null; then
    echo "${GREEN}✅ SSHFS can see project directory${NC}"
else
    echo "${YELLOW}⚠️  SSHFS test inconclusive (may still work normally)${NC}"
fi

# Summary
echo ""
echo "========================================="
echo "${GREEN}Setup Complete!${NC}"
echo "========================================="
echo ""
echo "Commands available:"
echo ""
echo "  ${YELLOW}Mount Widow project:${NC}"
echo "    ./scripts/mount_widow_project.sh"
echo ""
echo "  ${YELLOW}Unmount:${NC}"
echo "    ./scripts/mount_widow_project.sh unmount"
echo ""
echo "  ${YELLOW}Check status:${NC}"
echo "    ./scripts/mount_widow_project.sh status"
echo ""
echo "After running 'source ~/.bashrc', you can also use:"
echo "  - ${YELLOW}widow-mount${NC}     : Mount Widow project"
echo "  - ${YELLOW}widow-unmount${NC}   : Unmount"
echo "  - ${YELLOW}widow-status${NC}    : Check status"
echo "  - ${YELLOW}widow-project${NC}   : SSH into project directory"
echo "  - ${YELLOW}widow-code${NC}      : Open VS Code Remote to Widow"
echo ""
echo "Or use VS Code Remote SSH:"
echo "  code --remote ssh-remote+widow"
echo ""