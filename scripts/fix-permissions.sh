#!/bin/bash

# News Intelligence System v2.9.0 - Permanent Permission Fix
# This script creates a permanent solution for all permission issues

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
NAS_BASE="/mnt/terramaster-nas/docker-postgres-data"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${PURPLE}🔧 News Intelligence System - Permanent Permission Fix${NC}"
echo -e "${PURPLE}====================================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (use sudo)${NC}"
    echo -e "${YELLOW}   Run: sudo ./scripts/fix-permissions.sh${NC}"
    exit 1
fi

echo -e "${BLUE}📋 Creating permanent directory structure...${NC}"

# Create all required directories with proper structure
mkdir -p "$NAS_BASE"/{pgdata,backups,logs,redis-data,grafana-data,grafana-logs,prometheus-data,nginx-logs}

echo -e "${GREEN}✅ Directory structure created${NC}"

echo -e "${BLUE}🔐 Setting up permanent permission system...${NC}"

# Function to set permissions for a service
set_service_permissions() {
    local service_name="$1"
    local user_id="$2"
    local group_id="$3"
    local directories="$4"
    
    echo -e "${BLUE}   Setting permissions for $service_name (UID:$user_id GID:$group_id)...${NC}"
    
    # Create the user and group if they don't exist
    if ! getent group "$group_id" >/dev/null 2>&1; then
        groupadd -g "$group_id" "docker-$service_name" 2>/dev/null || true
    fi
    
    if ! getent passwd "$user_id" >/dev/null 2>&1; then
        useradd -u "$user_id" -g "$group_id" -r -s /bin/false "docker-$service_name" 2>/dev/null || true
    fi
    
    # Set ownership for directories
    for dir in $directories; do
        if [ -d "$dir" ]; then
            chown -R "$user_id:$group_id" "$dir"
            chmod -R 755 "$dir"
            echo -e "${GREEN}     ✅ $dir${NC}"
        else
            echo -e "${YELLOW}     ⚠️  $dir (not found, will be created by Docker)${NC}"
        fi
    done
}

# Set permissions for each service
set_service_permissions "postgres" "999" "999" "$NAS_BASE/pgdata $NAS_BASE/backups $NAS_BASE/logs"
set_service_permissions "grafana" "472" "472" "$NAS_BASE/grafana-data $NAS_BASE/grafana-logs"
set_service_permissions "prometheus" "65534" "65534" "$NAS_BASE/prometheus-data"
set_service_permissions "redis" "999" "999" "$NAS_BASE/redis-data"
set_service_permissions "nginx" "101" "101" "$NAS_BASE/nginx-logs"

echo -e "${GREEN}✅ Permission system configured${NC}"

echo -e "${BLUE}📁 Setting up project directory permissions...${NC}"

# Set permissions for project directories
chown -R "$(id -u):$(id -g)" "$PROJECT_DIR"/api/docker/monitoring
chmod -R 755 "$PROJECT_DIR"/api/docker/monitoring

# Ensure SSL directory has proper permissions
if [ -d "$PROJECT_DIR/api/docker/nginx/ssl" ]; then
    chown -R "$(id -u):$(id -g)" "$PROJECT_DIR/api/docker/nginx/ssl"
    chmod 755 "$PROJECT_DIR/api/docker/nginx/ssl"
    chmod 644 "$PROJECT_DIR/api/docker/nginx/ssl"/*.crt 2>/dev/null || true
    chmod 600 "$PROJECT_DIR/api/docker/nginx/ssl"/*.key 2>/dev/null || true
fi

echo -e "${GREEN}✅ Project directory permissions set${NC}"

echo -e "${BLUE}🔧 Creating persistent permission script...${NC}"

# Create a script that can be run to fix permissions after any changes
cat > "$PROJECT_DIR/scripts/ensure-permissions.sh" << 'EOF'
#!/bin/bash
# Auto-generated permission fix script
# Run this after any Docker operations that might affect permissions

set -e

NAS_BASE="/mnt/terramaster-nas/docker-postgres-data"

# Ensure directories exist
mkdir -p "$NAS_BASE"/{pgdata,backups,logs,redis-data,grafana-data,grafana-logs,prometheus-data,nginx-logs}

# Fix permissions
chown -R 999:999 "$NAS_BASE"/{pgdata,backups,logs,redis-data} 2>/dev/null || true
chown -R 472:472 "$NAS_BASE"/{grafana-data,grafana-logs} 2>/dev/null || true
chown -R 65534:65534 "$NAS_BASE"/prometheus-data 2>/dev/null || true
chown -R 101:101 "$NAS_BASE"/nginx-logs 2>/dev/null || true

# Set directory permissions
chmod -R 755 "$NAS_BASE" 2>/dev/null || true

echo "✅ Permissions ensured"
EOF

chmod +x "$PROJECT_DIR/scripts/ensure-permissions.sh"

echo -e "${GREEN}✅ Persistent permission script created${NC}"

echo -e "${BLUE}📋 Creating systemd service for automatic permission management...${NC}"

# Create a systemd service that ensures permissions on boot
cat > /etc/systemd/system/news-intel-permissions.service << EOF
[Unit]
Description=News Intelligence System Permission Manager
After=network.target

[Service]
Type=oneshot
ExecStart=$PROJECT_DIR/scripts/ensure-permissions.sh
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
systemctl daemon-reload
systemctl enable news-intel-permissions.service

echo -e "${GREEN}✅ Systemd service created and enabled${NC}"

echo -e "${BLUE}🔄 Running initial permission fix...${NC}"
"$PROJECT_DIR/scripts/ensure-permissions.sh"

echo ""
echo -e "${GREEN}🎉 Permanent permission system installed successfully!${NC}"
echo ""
echo -e "${PURPLE}📋 What was implemented:${NC}"
echo -e "${GREEN}   ✅ Proper user/group creation for all services${NC}"
echo -e "${GREEN}   ✅ Persistent directory structure with correct ownership${NC}"
echo -e "${GREEN}   ✅ Automatic permission restoration script${NC}"
echo -e "${GREEN}   ✅ Systemd service for boot-time permission management${NC}"
echo -e "${GREEN}   ✅ Project directory permissions configured${NC}"
echo ""
echo -e "${YELLOW}📋 Service User IDs:${NC}"
echo -e "${YELLOW}   • PostgreSQL: 999:999${NC}"
echo -e "${YELLOW}   • Grafana: 472:472${NC}"
echo -e "${YELLOW}   • Prometheus: 65534:65534${NC}"
echo -e "${YELLOW}   • Redis: 999:999${NC}"
echo -e "${YELLOW}   • Nginx: 101:101${NC}"
echo ""
echo -e "${BLUE}💡 Usage:${NC}"
echo -e "${BLUE}   • Run './scripts/ensure-permissions.sh' after any Docker operations${NC}"
echo -e "${BLUE}   • Permissions will be automatically restored on system boot${NC}"
echo -e "${BLUE}   • No more manual permission fixes needed!${NC}"
echo ""
echo -e "${GREEN}✨ Your News Intelligence System now has bulletproof permissions!${NC}"


