#!/bin/bash

# News Intelligence System v3.0 - Reboot and Restart Script
# Performs system reboot and restarts with RTX 5090 + 62GB RAM optimizations

echo "🔄 NEWS INTELLIGENCE SYSTEM v3.0 - REBOOT AND RESTART"
echo "====================================================="
echo "RTX 5090 + 62GB RAM Optimized Configuration"
echo "Started at: $(date)"
echo ""

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Change to project directory
cd "$PROJECT_DIR"

echo "📁 Project Directory: $PROJECT_DIR"
echo ""

# 1. PRE-REBOOT PREPARATION
echo "1. PRE-REBOOT PREPARATION"
echo "-------------------------"
echo "   Stopping all services..."

# Stop Docker services
docker-compose down 2>/dev/null || true

# Stop Ollama
pkill -f ollama 2>/dev/null || true

echo "   ✅ All services stopped"
echo ""

# 2. SAVE CURRENT STATE
echo "2. SAVE CURRENT STATE"
echo "---------------------"
echo "   Saving system state..."

# Create state backup
mkdir -p backups
cp ~/.config/ollama/ollama.env backups/ollama.env.backup 2>/dev/null || true
cp scripts/production/start_optimized_system.sh backups/start_optimized_system.sh.backup 2>/dev/null || true

echo "   ✅ System state saved"
echo ""

# 3. CREATE POST-REBOOT SCRIPT
echo "3. CREATE POST-REBOOT SCRIPT"
echo "----------------------------"
echo "   Creating post-reboot startup script..."

cat > /tmp/post_reboot_startup.sh << 'EOF'
#!/bin/bash

# Post-reboot startup script for News Intelligence System v3.0
# This script runs automatically after system reboot

echo "🚀 POST-REBOOT STARTUP - NEWS INTELLIGENCE SYSTEM v3.0"
echo "====================================================="
echo "RTX 5090 + 62GB RAM Optimized Configuration"
echo "Started at: $(date)"
echo ""

# Wait for system to fully boot
echo "⏳ Waiting for system to fully boot..."
sleep 30

# Change to project directory
cd "/home/pete/Documents/projects/Projects/News Intelligence"

# Start optimized system
echo "🚀 Starting optimized system..."
./scripts/production/start_optimized_system.sh

echo ""
echo "✅ POST-REBOOT STARTUP COMPLETE"
echo "==============================="
echo "System restarted at: $(date)"
echo ""

# Remove this script after execution
rm -f /tmp/post_reboot_startup.sh
EOF

chmod +x /tmp/post_reboot_startup.sh

echo "   ✅ Post-reboot script created"
echo ""

# 4. SCHEDULE POST-REBOOT EXECUTION
echo "4. SCHEDULE POST-REBOOT EXECUTION"
echo "---------------------------------"
echo "   Scheduling post-reboot startup..."

# Add to crontab for one-time execution after reboot
(crontab -l 2>/dev/null; echo "@reboot /tmp/post_reboot_startup.sh") | crontab -

echo "   ✅ Post-reboot startup scheduled"
echo ""

# 5. SYSTEM REBOOT
echo "5. SYSTEM REBOOT"
echo "----------------"
echo "   Initiating system reboot..."
echo ""
echo "⚠️  WARNING: System will reboot in 10 seconds!"
echo "   Press Ctrl+C to cancel"
echo ""

# Countdown
for i in {10..1}; do
    echo "   Rebooting in $i seconds..."
    sleep 1
done

echo ""
echo "🔄 REBOOTING SYSTEM NOW..."
echo "=========================="
echo "The system will restart automatically with optimized configuration."
echo "Check the system after reboot to verify all services are running."
echo ""

# Reboot system
sudo reboot

EOF

chmod +x /tmp/post_reboot_startup.sh

echo "   ✅ Post-reboot script created"
echo ""

# 4. SCHEDULE POST-REBOOT EXECUTION
echo "4. SCHEDULE POST-REBOOT EXECUTION"
echo "---------------------------------"
echo "   Scheduling post-reboot startup..."

# Add to crontab for one-time execution after reboot
(crontab -l 2>/dev/null; echo "@reboot /tmp/post_reboot_startup.sh") | crontab -

echo "   ✅ Post-reboot startup scheduled"
echo ""

# 5. SYSTEM REBOOT
echo "5. SYSTEM REBOOT"
echo "----------------"
echo "   Initiating system reboot..."
echo ""
echo "⚠️  WARNING: System will reboot in 10 seconds!"
echo "   Press Ctrl+C to cancel"
echo ""

# Countdown
for i in {10..1}; do
    echo "   Rebooting in $i seconds..."
    sleep 1
done

echo ""
echo "🔄 REBOOTING SYSTEM NOW..."
echo "=========================="
echo "The system will restart automatically with optimized configuration."
echo "Check the system after reboot to verify all services are running."
echo ""

# Reboot system
sudo reboot
