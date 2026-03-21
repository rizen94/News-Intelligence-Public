#!/bin/bash
# Script to run ON NAS to export SSH keys
# Run this on the NAS to get existing SSH keys

echo "🔑 Exporting SSH Keys from NAS"
echo "=============================="
echo ""

NAS_USER_HOME="/home/Admin"
if [ -d "$NAS_USER_HOME" ]; then
    SSH_DIR="$NAS_USER_HOME/.ssh"
else
    SSH_DIR="~/.ssh"
fi

echo "Checking for SSH keys in: $SSH_DIR"
echo ""

# Check for authorized_keys
if [ -f "$SSH_DIR/authorized_keys" ]; then
    echo "=== Authorized Keys (keys that can connect TO this NAS) ==="
    cat "$SSH_DIR/authorized_keys"
    echo ""
    echo "=== Saving to file ==="
    cat "$SSH_DIR/authorized_keys" > /tmp/nas_authorized_keys.txt
    echo "Saved to: /tmp/nas_authorized_keys.txt"
    echo ""
fi

# Check for public keys
echo "=== Public Keys on NAS ==="
for key in "$SSH_DIR"/*.pub; do
    if [ -f "$key" ]; then
        echo ""
        echo "Key: $key"
        echo "Type: $(ssh-keygen -l -f "$key" 2>/dev/null | awk '{print $4}')"
        echo "Fingerprint: $(ssh-keygen -lf "$key" 2>/dev/null | awk '{print $2}')"
        echo "Content:"
        cat "$key"
        echo ""
        # Save to file
        cp "$key" "/tmp/$(basename $key)"
        echo "Saved to: /tmp/$(basename $key)"
    fi
done

# Check for private keys (show fingerprint only, not content)
echo ""
echo "=== Private Keys on NAS (fingerprints only) ==="
for key in "$SSH_DIR"/id_*; do
    if [ -f "$key" ] && [[ ! "$key" == *.pub ]]; then
        echo ""
        echo "Key: $key"
        if [ -f "$key.pub" ]; then
            echo "Fingerprint: $(ssh-keygen -lf "$key.pub" 2>/dev/null | awk '{print $2}')"
            echo "Type: $(ssh-keygen -l -f "$key.pub" 2>/dev/null | awk '{print $4}')"
        else
            echo "No matching public key found"
        fi
    fi
done

echo ""
echo "✅ Key export complete!"
echo ""
echo "📁 Files saved to /tmp/ on NAS:"
ls -lh /tmp/nas_* /tmp/id_* 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'
echo ""
echo "💡 To copy these files to your local machine:"
echo "   scp -P 9222 Admin@192.168.93.100:/tmp/nas_authorized_keys.txt ~/"
echo "   scp -P 9222 Admin@192.168.93.100:/tmp/id_*.pub ~/.ssh/"

