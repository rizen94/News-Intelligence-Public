# Persistent NAS Storage Setup Guide

## Overview
This guide explains how to set up a persistent, auto-reconnecting NAS mount for the News Intelligence System. The NAS will be automatically mounted on boot and will reconnect if the connection drops.

## Quick Setup

Run the setup script:
```bash
./scripts/setup_persistent_nas_mount.sh
```

This will:
1. Create mount point at `/mnt/nas`
2. Create secure credentials file
3. Add to `/etc/fstab` for auto-mount
4. Create systemd services for monitoring
5. Test the mount
6. Create directory structure on NAS

## What Gets Configured

### 1. Mount Point
- **Location**: `/mnt/nas`
- **Type**: CIFS/SMB
- **Auto-mount**: Yes (via fstab)

### 2. Credentials
- **File**: `/etc/nas-credentials` (secured, 600 permissions)
- **Contains**: Username, password, domain
- **Access**: Root only

### 3. Auto-Mount (fstab)
Entry in `/etc/fstab`:
```
//192.168.93.100/public /mnt/nas cifs credentials=/etc/nas-credentials,uid=1000,gid=1000,iocharset=utf8,file_mode=0777,dir_mode=0777,vers=3.0,_netdev,auto,user,noauto 0 0
```

### 4. Systemd Services

#### nas-mount.service
- **Purpose**: Mount NAS on boot
- **Triggers**: After network is online
- **Retry**: On failure, retries every 30 seconds
- **Status**: `sudo systemctl status nas-mount.service`

#### nas-mount-monitor.service
- **Purpose**: Monitor mount health and auto-reconnect
- **Checks**: Every 60 seconds
- **Action**: Remounts if connection lost
- **Status**: `sudo systemctl status nas-mount-monitor.service`

## Directory Structure on NAS

After setup, the following directories are created:
```
/mnt/nas/news-intelligence/
├── postgres-data/    # PostgreSQL database files
├── logs/             # Application logs
├── backups/          # Database backups
├── ml-models/        # ML model storage
└── data-archives/    # Historical data
```

## Usage

### Manual Mount
```bash
sudo mount /mnt/nas
```

### Manual Unmount
```bash
sudo umount /mnt/nas
```

### Check Mount Status
```bash
mountpoint /mnt/nas
df -h /mnt/nas
```

### Service Management
```bash
# Start services
sudo systemctl start nas-mount.service
sudo systemctl start nas-mount-monitor.service

# Stop services
sudo systemctl stop nas-mount.service
sudo systemctl stop nas-mount-monitor.service

# Check status
sudo systemctl status nas-mount.service
sudo systemctl status nas-mount-monitor.service

# View logs
sudo journalctl -u nas-mount.service -f
sudo journalctl -u nas-mount-monitor.service -f
```

## Integration with News Intelligence System

### Database Storage
Update `start_system.sh` to use NAS for PostgreSQL data:
```bash
export DB_HOST=192.168.93.100
export DB_PORT=5432
```

### Log Storage
Logs can be written directly to `/mnt/nas/news-intelligence/logs/`

### Backup Storage
Backups can be stored in `/mnt/nas/news-intelligence/backups/`

## Troubleshooting

### Mount Fails on Boot
1. Check network is up: `ping 192.168.93.100`
2. Check credentials: `sudo cat /etc/nas-credentials`
3. Check fstab entry: `cat /etc/fstab | grep nas`
4. Check service logs: `sudo journalctl -u nas-mount.service`

### Connection Drops
The monitor service should automatically reconnect. Check:
```bash
sudo systemctl status nas-mount-monitor.service
sudo journalctl -u nas-mount-monitor.service -f
```

### Permission Issues
Ensure mount has correct UID/GID:
```bash
ls -la /mnt/nas
# Should show your user as owner
```

### Manual Remount
If automatic remount fails:
```bash
sudo umount /mnt/nas
sudo mount /mnt/nas
```

## Security Notes

1. **Credentials File**: Stored in `/etc/nas-credentials` with 600 permissions (root only)
2. **Network**: NAS should be on trusted network
3. **Firewall**: Consider restricting access to NAS IP
4. **Backup**: Keep credentials backed up securely

## Configuration Details

### NAS Connection
- **Host**: 192.168.93.100
- **Share**: public
- **User**: Admin
- **Domain**: LAKEHOUSE
- **Protocol**: SMB/CIFS v3.0

### Mount Options
- `_netdev`: Wait for network before mounting
- `auto`: Auto-mount on boot
- `user`: Allow users to mount
- `noauto`: Don't auto-mount (use systemd service instead)
- `vers=3.0`: Use SMB 3.0 protocol
- `file_mode=0777`: File permissions
- `dir_mode=0777`: Directory permissions

## Next Steps

After setting up persistent mount:

1. **Copy migration files**:
   ```bash
   ./scripts/copy_files_to_nas.sh
   ```

2. **Set up PostgreSQL on NAS**:
   - Follow `QUICK_START.md` in migration backup directory

3. **Update system configuration**:
   - Set `DB_HOST=192.168.93.100` in environment
   - Update `start_system.sh` to use NAS database

4. **Verify everything works**:
   ```bash
   sudo systemctl status nas-mount.service
   df -h /mnt/nas
   ls -la /mnt/nas/news-intelligence/
   ```

## Maintenance

### Update Credentials
If NAS password changes:
```bash
sudo nano /etc/nas-credentials
# Update password
sudo systemctl restart nas-mount.service
```

### Disable Auto-Mount
```bash
sudo systemctl disable nas-mount.service
sudo systemctl disable nas-mount-monitor.service
```

### Remove Configuration
```bash
sudo systemctl stop nas-mount-monitor.service
sudo systemctl stop nas-mount.service
sudo systemctl disable nas-mount-monitor.service
sudo systemctl disable nas-mount.service
sudo umount /mnt/nas
sudo sed -i '/\/mnt\/nas/d' /etc/fstab
sudo rm /etc/nas-credentials
```

