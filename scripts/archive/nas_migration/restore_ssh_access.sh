#!/bin/bash
# Restore SSH Access via Telnet
# Fixes SSH lockout by resetting fail2ban or SSH configuration

NAS_HOST="192.168.93.100"
TELNET_PORT="2332"
NAS_USER="Admin"
NAS_PASSWORD="<NAS_PASSWORD_PLACEHOLDER>"

echo "🔧 Restoring SSH Access via Telnet"
echo "==================================="
echo ""
echo "Connecting to NAS via telnet (port $TELNET_PORT)..."
echo ""

# Create expect script for telnet interaction
expect << EOF
set timeout 10
spawn telnet $NAS_HOST $TELNET_PORT

expect {
    "login:" {
        send "$NAS_USER\r"
        exp_continue
    }
    "Login:" {
        send "$NAS_USER\r"
        exp_continue
    }
    "Username:" {
        send "$NAS_USER\r"
        exp_continue
    }
    "Password:" {
        send "$NAS_PASSWORD\r"
        exp_continue
    }
    "password:" {
        send "$NAS_PASSWORD\r"
        exp_continue
    }
    "# " {
        send "echo 'Connected successfully'\r"
        exp_continue
    }
    "$ " {
        send "echo 'Connected successfully'\r"
        exp_continue
    }
    ">" {
        send "echo 'Connected successfully'\r"
        exp_continue
    }
}

# Once logged in, fix SSH settings
expect {
    "# " {
        send "whoami\r"
        expect "# "
        send "pwd\r"
        expect "# "
        
        # Check if fail2ban is running
        send "systemctl status fail2ban 2>&1 | head -5\r"
        expect "# "
        
        # Stop fail2ban if running
        send "systemctl stop fail2ban 2>&1\r"
        expect "# "
        
        # Unban IP addresses
        send "fail2ban-client unban --all 2>&1 || echo 'fail2ban not available'\r"
        expect "# "
        
        # Check SSH config
        send "grep -E 'MaxAuthTries|PermitRootLogin|PasswordAuthentication' /etc/ssh/sshd_config 2>&1 | head -10\r"
        expect "# "
        
        # Reset SSH config to allow access
        send "sed -i 's/^MaxAuthTries.*/MaxAuthTries 10/' /etc/ssh/sshd_config 2>&1\r"
        expect "# "
        send "sed -i 's/^#MaxAuthTries.*/MaxAuthTries 10/' /etc/ssh/sshd_config 2>&1\r"
        expect "# "
        send "grep -q '^MaxAuthTries' /etc/ssh/sshd_config || echo 'MaxAuthTries 10' >> /etc/ssh/sshd_config\r"
        expect "# "
        
        # Restart SSH service
        send "systemctl restart sshd 2>&1 || service ssh restart 2>&1 || /etc/init.d/ssh restart 2>&1\r"
        expect "# "
        
        # Verify SSH is running
        send "systemctl status sshd 2>&1 | head -3 || netstat -tlnp | grep :9222 || ss -tlnp | grep :9222\r"
        expect "# "
        
        send "echo 'SSH access restored'\r"
        expect "# "
        send "exit\r"
    }
    "$ " {
        send "sudo whoami\r"
        expect {
            "password" {
                send "$NAS_PASSWORD\r"
                exp_continue
            }
            "# " {
                # Same commands as above but with sudo
                send "sudo systemctl stop fail2ban 2>&1\r"
                expect "# "
                send "sudo fail2ban-client unban --all 2>&1 || echo 'fail2ban not available'\r"
                expect "# "
                send "sudo sed -i 's/^MaxAuthTries.*/MaxAuthTries 10/' /etc/ssh/sshd_config 2>&1\r"
                expect "# "
                send "sudo systemctl restart sshd 2>&1\r"
                expect "# "
                send "exit\r"
            }
        }
    }
    timeout {
        puts "Connection timed out"
        exit 1
    }
    eof
}

EOF

echo ""
echo "✅ SSH access restoration attempt complete"
echo ""
echo "Testing SSH connection..."
sleep 2
if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p 9222 Admin@192.168.93.100 "echo 'SSH test successful'" 2>&1 | grep -q "SSH test successful"; then
    echo "✅ SSH access restored!"
else
    echo "⚠️  SSH may still need manual configuration"
    echo "Connect via telnet and run these commands:"
    echo "  systemctl stop fail2ban"
    echo "  fail2ban-client unban --all"
    echo "  systemctl restart sshd"
fi

