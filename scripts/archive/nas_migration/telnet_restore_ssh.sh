#!/bin/bash
# Manual Telnet Commands to Restore SSH Access
# Run these commands after connecting via telnet

cat << 'EOF'
==========================================
Telnet Commands to Restore SSH Access
==========================================

1. Connect to NAS:
   telnet 192.168.93.100 2332

2. Login:
   Username: Admin
   Password: Pooter@STORAGE2024

3. Once logged in, run these commands:

   # Check current user
   whoami
   
   # Check if fail2ban is running
   systemctl status fail2ban
   # OR
   service fail2ban status
   
   # Stop fail2ban
   systemctl stop fail2ban
   # OR
   service fail2ban stop
   
   # Unban all IPs
   fail2ban-client unban --all
   
   # Check SSH configuration
   cat /etc/ssh/sshd_config | grep -E "MaxAuthTries|PermitRootLogin|PasswordAuthentication"
   
   # Increase MaxAuthTries
   sed -i 's/^MaxAuthTries.*/MaxAuthTries 10/' /etc/ssh/sshd_config
   sed -i 's/^#MaxAuthTries.*/MaxAuthTries 10/' /etc/ssh/sshd_config
   
   # If MaxAuthTries doesn't exist, add it
   grep -q "^MaxAuthTries" /etc/ssh/sshd_config || echo "MaxAuthTries 10" >> /etc/ssh/sshd_config
   
   # Restart SSH service
   systemctl restart sshd
   # OR
   service ssh restart
   # OR
   /etc/init.d/ssh restart
   
   # Verify SSH is running
   systemctl status sshd
   netstat -tlnp | grep :9222
   
   # Test SSH connection
   exit
   ssh -p 9222 Admin@192.168.93.100 "echo 'SSH restored'"

==========================================
Alternative: Reset via iptables
==========================================

If fail2ban uses iptables:

   # List iptables rules
   iptables -L -n | grep -A 5 fail2ban
   
   # Flush fail2ban chain
   iptables -F f2b-sshd
   
   # Or remove fail2ban rules
   iptables -D INPUT -p tcp --dport 9222 -j f2b-sshd

==========================================
EOF

