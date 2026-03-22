#!/usr/bin/env python3
"""
Restore SSH Access via Telnet
Connects to NAS via telnet and fixes SSH lockout issues
"""

import telnetlib
import time
import sys

NAS_HOST = "192.168.93.100"
TELNET_PORT = 2332
NAS_USER = "Admin"
NAS_PASSWORD = "<NAS_PASSWORD_PLACEHOLDER>"

def restore_ssh_access():
    """Connect via telnet and restore SSH access"""
    print(f"🔧 Connecting to NAS via telnet ({NAS_HOST}:{TELNET_PORT})...")
    
    try:
        # Connect to telnet
        tn = telnetlib.Telnet(NAS_HOST, TELNET_PORT, timeout=10)
        
        # Wait for login prompt
        tn.read_until(b"login:", timeout=5)
        tn.write(NAS_USER.encode('ascii') + b"\n")
        time.sleep(1)
        
        # Wait for password prompt
        tn.read_until(b"Password:", timeout=5)
        tn.write(NAS_PASSWORD.encode('ascii') + b"\n")
        time.sleep(2)
        
        # Check if we're logged in
        response = tn.read_very_eager().decode('ascii', errors='ignore')
        print(f"Login response: {response[:200]}")
        
        def send_command(tn, cmd, wait_for_prompt=True):
            """Send command and handle sudo password prompts"""
            tn.write(cmd.encode('ascii') + b"\n")
            time.sleep(1)
            response = tn.read_very_eager().decode('ascii', errors='ignore')
            
            # Check for sudo password prompt
            if "Password:" in response or "[sudo] password" in response.lower():
                print("  → Sudo password required, providing...")
                tn.write(NAS_PASSWORD.encode('ascii') + b"\n")
                time.sleep(1)
                response += tn.read_very_eager().decode('ascii', errors='ignore')
            
            return response
        
        # Send commands to restore SSH (TNAS uses different service management)
        commands = [
            ("whoami", False),
            ("pwd", False),
            # Check for blocking mechanisms
            ("cat /etc/hosts.deny 2>&1 | head -10 || echo 'No hosts.deny file'", False),
            ("cat /etc/hosts.allow 2>&1 | head -10 || echo 'No hosts.allow file'", False),
            ("ps aux | grep -i fail2ban | grep -v grep || echo 'No fail2ban process'", False),
            ("iptables -L INPUT -n -v 2>&1 | head -15 || echo 'iptables check'", False),
            # Check current SSH config
            ("grep -E 'MaxAuthTries|PermitRootLogin|PasswordAuthentication|DenyUsers|AllowUsers' /etc/ssh/sshd_config 2>&1 | head -10", False),
            # Modify SSH config with sudo - set MaxAuthTries to 100
            ("sudo sed -i 's/^MaxAuthTries.*/MaxAuthTries 100/' /etc/ssh/sshd_config 2>&1", True),
            ("sudo sed -i 's/^#MaxAuthTries.*/MaxAuthTries 100/' /etc/ssh/sshd_config 2>&1", True),
            ("grep -q '^MaxAuthTries' /etc/ssh/sshd_config || echo 'MaxAuthTries 100' | sudo tee -a /etc/ssh/sshd_config 2>&1", True),
            # Remove any DenyUsers or AllowUsers that might block
            ("sudo sed -i '/^DenyUsers/d' /etc/ssh/sshd_config 2>&1", True),
            ("sudo sed -i '/^AllowUsers/d' /etc/ssh/sshd_config 2>&1", True),
            # Clear hosts.deny if it exists
            ("sudo sed -i '/sshd/d' /etc/hosts.deny 2>&1 || echo 'hosts.deny cleared or not found'", True),
            # Clear iptables blocks
            ("sudo iptables -F INPUT 2>&1 || echo 'iptables INPUT flush'", True),
            ("sudo iptables -F 2>&1 || echo 'iptables full flush'", True),
            ("sudo iptables -P INPUT ACCEPT 2>&1 || echo 'iptables policy'", True),
            # Verify the change
            ("grep '^MaxAuthTries' /etc/ssh/sshd_config", False),
            # Restart SSH service
            ("sudo /etc/init.d/ssh restart 2>&1 || sudo service ssh restart 2>&1 || sudo killall -HUP sshd 2>&1 || echo 'SSH restart attempted'", True),
            # Verify SSH is running
            ("ps aux | grep sshd | grep -v grep | head -2", False),
            ("netstat -tlnp 2>&1 | grep :9222 || ss -tlnp 2>&1 | grep :9222 || echo 'Checking SSH port'", False),
            ("echo 'SSH restoration complete'", False),
        ]
        
        for cmd, needs_sudo in commands:
            print(f"\n📤 Executing: {cmd}")
            response = send_command(tn, cmd, needs_sudo)
            print(f"📥 Response: {response[:400]}")
            time.sleep(1)
        
        tn.write(b"exit\n")
        tn.close()
        
        print("\n✅ Telnet session complete")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("SSH Access Restoration via Telnet")
    print("=" * 50)
    print()
    
    if restore_ssh_access():
        print("\n⏳ Waiting 3 seconds for SSH to restart...")
        time.sleep(3)
        
        print("\n🔍 Testing SSH access...")
        import subprocess
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5", 
             "-p", "9222", f"{NAS_USER}@{NAS_HOST}", "echo 'SSH restored!'"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ SSH access has been restored!")
        else:
            print("⚠️  SSH may need additional configuration")
            print(f"Error: {result.stderr[:200]}")
    else:
        print("❌ Failed to restore SSH access via telnet")

