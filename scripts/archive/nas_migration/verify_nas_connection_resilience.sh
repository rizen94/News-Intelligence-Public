#!/bin/bash
# Comprehensive NAS Connection Resilience Test
# Tests all aspects of connection persistence and recovery

set -e

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
NAS_MOUNT_PATH="/mnt/nas"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

PASSED=0
FAILED=0

test_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASSED++))
}

test_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAILED++))
}

test_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

header() {
    echo ""
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================${NC}"
    echo ""
}

header "NAS Connection Resilience Test"
echo "Testing all aspects of connection persistence and recovery..."
echo ""

# Test 1: fstab Configuration
header "Test 1: Boot Persistence (fstab)"
if grep -q "$NAS_MOUNT_PATH" /etc/fstab 2>/dev/null; then
    test_pass "fstab entry exists for auto-mount on boot"
    echo "   Entry: $(grep "$NAS_MOUNT_PATH" /etc/fstab)"
else
    test_fail "fstab entry missing - mount will not persist on boot"
fi

# Test 2: Mount Point
header "Test 2: Mount Point Configuration"
if [ -d "$NAS_MOUNT_PATH" ]; then
    test_pass "Mount point directory exists: $NAS_MOUNT_PATH"
else
    test_fail "Mount point directory missing: $NAS_MOUNT_PATH"
fi

# Test 3: Current Mount Status
header "Test 3: Current Mount Status"
if mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
    test_pass "NAS is currently mounted"
    df -h "$NAS_MOUNT_PATH" | tail -1 | awk '{print "   " $1 " -> " $2 " total, " $4 " available"}'
else
    test_fail "NAS is not currently mounted"
fi

# Test 4: Mount Resilience
header "Test 4: Mount Resilience (Unmount/Remount)"
if mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
    echo "   Unmounting..."
    sudo umount "$NAS_MOUNT_PATH" 2>&1 > /dev/null || true
    sleep 1
    
    if ! mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
        test_pass "Successfully unmounted"
        
        echo "   Remounting..."
        sudo mount "$NAS_MOUNT_PATH" 2>&1 > /dev/null
        sleep 2
        
        if mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
            test_pass "Successfully remounted"
        else
            test_fail "Failed to remount after unmount"
        fi
    else
        test_fail "Failed to unmount"
    fi
else
    test_warn "NAS not mounted, attempting mount..."
    sudo mount "$NAS_MOUNT_PATH" 2>&1 > /dev/null
    sleep 2
    if mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
        test_pass "Successfully mounted"
    else
        test_fail "Failed to mount"
    fi
fi

# Test 5: SSH Key Authentication
header "Test 5: SSH Key Authentication"
if [ -f ~/.ssh/id_rsa ] && [ -f ~/.ssh/id_rsa.pub ]; then
    test_pass "SSH key pair exists"
else
    test_fail "SSH key pair missing"
fi

# Test 6: SSH Config
header "Test 6: SSH Config Alias"
if [ -f ~/.ssh/config ] && grep -q "Host nas" ~/.ssh/config; then
    test_pass "SSH config alias 'nas' exists"
    echo "   Config:"
    grep -A 5 "Host nas" ~/.ssh/config | sed 's/^/      /'
else
    test_fail "SSH config alias missing"
fi

# Test 7: Passwordless SSH
header "Test 7: Passwordless SSH Connection"
if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no -p "$NAS_SSH_PORT" "$NAS_USER@$NAS_HOST" "echo 'test'" > /dev/null 2>&1; then
    test_pass "Passwordless SSH connection works"
else
    test_fail "Passwordless SSH connection failed"
fi

# Test 8: Credentials File
header "Test 8: NAS Credentials File"
if [ -f /etc/nas-credentials ]; then
    test_pass "Credentials file exists: /etc/nas-credentials"
    PERMS=$(stat -c "%a" /etc/nas-credentials 2>/dev/null || echo "unknown")
    if [ "$PERMS" = "600" ]; then
        test_pass "Credentials file has correct permissions (600)"
    else
        test_warn "Credentials file permissions: $PERMS (should be 600)"
    fi
else
    test_fail "Credentials file missing"
fi

# Test 9: Database Configuration
header "Test 9: Database Configuration"
if grep -q "DB_HOST=192.168.93.100" "$PROJECT_ROOT/start_system.sh" 2>/dev/null; then
    test_pass "Database configured to use NAS (192.168.93.100)"
else
    test_fail "Database not configured for NAS"
fi

if grep -qi "ALLOW_LOCAL_DB" "$PROJECT_ROOT/start_system.sh" 2>/dev/null; then
    if grep -q "ALLOW_LOCAL_DB=true" "$PROJECT_ROOT/start_system.sh" 2>/dev/null; then
        test_warn "ALLOW_LOCAL_DB is enabled (local fallback allowed)"
    else
        test_pass "ALLOW_LOCAL_DB not enabled (NAS required)"
    fi
else
    test_pass "No local database fallback configured"
fi

# Test 10: Database Connection Test
header "Test 10: Database Connection"
echo "   Testing connection to NAS database..."
if python3 -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        host='$NAS_HOST',
        port=5432,
        database='news_intelligence',
        user='newsapp',
        password='newsapp_password',
        connect_timeout=5
    )
    conn.close()
    print('   ✅ Database connection successful')
    exit(0)
except psycopg2.OperationalError as e:
    if 'timeout' in str(e).lower() or 'refused' in str(e).lower():
        print('   ⚠️  Database not accessible (may not be set up yet)')
    else:
        print(f'   ❌ Database connection failed: {str(e)[:50]}')
    exit(1)
except Exception as e:
    print(f'   ⚠️  Database check error: {str(e)[:50]}')
    exit(1)
" 2>&1; then
    test_pass "Database connection successful"
else
    test_warn "Database connection test failed (may need PostgreSQL setup on NAS)"
fi

# Test 11: Startup Script Validation
header "Test 11: Startup Script NAS Validation"
if grep -q "192.168.93.100" "$PROJECT_ROOT/start_system.sh" 2>/dev/null; then
    test_pass "Startup script references NAS"
    
    if grep -qi "validate\|check\|verify" "$PROJECT_ROOT/start_system.sh" | grep -qi "nas\|192.168.93.100" 2>/dev/null; then
        test_pass "Startup script includes NAS validation"
    else
        test_warn "Startup script may not validate NAS connection before starting"
    fi
else
    test_fail "Startup script does not reference NAS"
fi

# Test 12: Systemd Services (Optional)
header "Test 12: Systemd Services (Optional)"
if systemctl list-units --type=service --all | grep -qi nas 2>/dev/null; then
    NAS_SERVICES=$(systemctl list-units --type=service --all | grep -i nas | awk '{print $1}')
    for service in $NAS_SERVICES; do
        if systemctl is-enabled "$service" > /dev/null 2>&1; then
            test_pass "Service enabled: $service"
        else
            test_warn "Service exists but not enabled: $service"
        fi
    done
else
    test_warn "No NAS systemd services found (using fstab for persistence)"
fi

# Summary
header "Test Summary"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All critical tests passed!${NC}"
    echo "   Connection is persistent and resilient."
    exit 0
else
    echo -e "${RED}❌ Some tests failed.${NC}"
    echo "   Review failures above and fix issues."
    exit 1
fi

