#!/bin/bash
# Setup SSH Key Authentication for NAS

NAS_HOST="192.168.93.100"
NAS_SSH_PORT="9222"
NAS_USER="Admin"
KEY_FILE="$HOME/.ssh/nas_key"

echo "🔐 Setting up SSH Key Authentication for NAS"
echo "============================================="
echo ""

# Generate SSH key if it doesn't exist
if [ ! -f "$KEY_FILE" ]; then
    echo "Generating SSH key..."
    ssh-keygen -t rsa -b 4096 -f "$KEY_FILE" -N "" -C "nas-postgres-migration"
    success "SSH key generated: $KEY_FILE"
else
    echo "SSH key already exists: $KEY_FILE"
fi

# Copy public key to NAS
echo ""
echo "Copying public key to NAS..."
echo "You may be prompted for the NAS password:"
echo ""

if ssh-copy-id -i "${KEY_FILE}.pub" -p "$NAS_SSH_PORT" "${NAS_USER}@${NAS_HOST}" 2>&1; then
    echo ""
    echo "✅ SSH key copied successfully!"
    echo ""
    echo "Testing connection..."
    if ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -p "$NAS_SSH_PORT" \
        "${NAS_USER}@${NAS_HOST}" "echo 'Connection successful!' && whoami && hostname" 2>&1; then
        echo ""
        echo "✅ SSH key authentication working!"
        echo ""
        echo "📝 Update scripts to use:"
        echo "   ssh -i $KEY_FILE -p $NAS_SSH_PORT ${NAS_USER}@${NAS_HOST}"
    else
        echo "❌ Connection test failed"
        exit 1
    fi
else
    echo ""
    echo "❌ Failed to copy SSH key"
    echo ""
    echo "💡 Manual steps:"
    echo "   1. Copy public key content:"
    echo "      cat ${KEY_FILE}.pub"
    echo ""
    echo "   2. On NAS, add to ~/.ssh/authorized_keys:"
    echo "      ssh -p $NAS_SSH_PORT ${NAS_USER}@${NAS_HOST}"
    echo "      mkdir -p ~/.ssh"
    echo "      echo 'PASTE_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys"
    echo "      chmod 600 ~/.ssh/authorized_keys"
    exit 1
fi

