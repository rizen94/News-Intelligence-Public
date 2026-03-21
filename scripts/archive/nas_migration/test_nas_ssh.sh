#!/bin/bash
# Test SSH Connection to NAS on Port 9222

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
NAS_PASSWORD="Pooter@STORAGE2024"

echo "🔍 Testing SSH Connection to NAS"
echo "================================="
echo ""
echo "Host: ${NAS_USER}@${NAS_HOST}:${NAS_SSH_PORT}"
echo ""

# Test port connectivity
echo "1. Testing port connectivity..."
if timeout 3 bash -c "echo > /dev/tcp/${NAS_HOST}/${NAS_SSH_PORT}" 2>/dev/null; then
    echo "   ✅ Port ${NAS_SSH_PORT} is open"
else
    echo "   ❌ Port ${NAS_SSH_PORT} is closed"
    exit 1
fi

# Test SSH connection with password
echo ""
echo "2. Testing SSH connection with password..."
if command -v sshpass &> /dev/null; then
    if sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "echo 'Connection successful!' && whoami && hostname && uname -a" 2>&1; then
        echo "   ✅ SSH connection successful with password"
        echo ""
        echo "3. Testing Docker availability..."
        sshpass -p "$NAS_PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
            "${NAS_USER}@${NAS_HOST}" "command -v docker && docker --version && docker ps" 2>&1
        echo ""
        echo "✅ Ready to proceed with PostgreSQL setup!"
        exit 0
    else
        echo "   ❌ SSH connection failed with password"
        echo ""
        echo "   Trying key-based authentication..."
        if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
            "${NAS_USER}@${NAS_HOST}" "echo 'Connection successful!' && whoami" 2>&1; then
            echo "   ✅ SSH connection successful with key"
            exit 0
        else
            echo "   ❌ SSH connection failed"
            echo ""
            echo "💡 Possible solutions:"
            echo "   1. Verify password is correct"
            echo "   2. Set up SSH key authentication"
            echo "   3. Check NAS SSH settings"
            exit 1
        fi
    fi
else
    echo "   ⚠️  sshpass not installed. Trying key-based authentication..."
    if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "echo 'Connection successful!' && whoami && hostname" 2>&1; then
        echo "   ✅ SSH connection successful with key"
        exit 0
    else
        echo "   ❌ SSH connection failed"
        echo ""
        echo "💡 Install sshpass or set up SSH keys:"
        echo "   sudo apt-get install sshpass"
        exit 1
    fi
fi

