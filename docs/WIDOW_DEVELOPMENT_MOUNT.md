# Widow Server Development Mount

Quick access to the Widow server's News Intelligence project without SSH overhead.

## Quick Start

### Option 1: VS Code Remote SSH (Recommended for Coding)

The easiest solution for editing files and running commands:

```bash
# Open VS Code connected to Widow
code --remote ssh-remote+widow

# Or use the command palette:
# Ctrl+Shift+P → "Remote-SSH: Connect to Host..." → select "widow"
```

**Benefits:**
- Edit files directly on Widow
- Terminal automatically runs on Widow
- Full IntelliSense, debugging on the remote server
- No setup required (VS Code Remote SSH extension)

---

### Option 2: SSHFS Mount (Recommended for CLI/Scripts)

Mount Widow's project folder locally for seamless access:

```bash
# Mount the project
./scripts/mount_widow_project.sh

# Access files locally
cd ~/widow-news-intel
ls  # Shows the News Intelligence project from Widow

# Unmount when done
./scripts/mount_widow_project.sh unmount
```

---

### Option 3: Auto-Mount at Login

Add this to your `~/.bashrc` or `~/.zshrc`:

```bash
# Add Widow project mount and aliases
source ~/Documents/projects/News\ Intelligence/scripts/widow_dev_aliases.sh
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

---

## Configuration Details

| Setting | Value |
|-|---|
| **Widow Host** | `192.168.93.101` |
| **Username** | `pete` |
| **Project Path (on Widow)** | `/home/pete/Documents/projects/News Intelligence` (canonical dev) |
| **Production runtime** | `/opt/news-intelligence` (API may run from here) |
| **Deprecated** | `/home/pete/projects/News Intelligence` — do not use |
| **Local Mount Point** | `~/widow-news-intel` |
| **SSH Alias** | `widow` |

---

## Commands Reference

### Mount Commands
```bash
# Mount Widow project
./scripts/mount_widow_project.sh

# Check mount status
./scripts/mount_widow_project.sh status

# Unmount
./scripts/mount_widow_project.sh unmount
```

### Quick Access Aliases (after sourcing widow_dev_aliases.sh)
```bash
# Mount Widow project
widow-mount

# Unmount Widow project
widow-unmount

# Check status
widow-status

# CD to mounted project (if mounted)
widow-cd

# SSH directly into project directory
widow-project

# Open VS Code Remote to Widow
widow-code
```

---

## Performance Considerations

### SSHFS (Used by default)
- **Pros:** Easy setup, works over SSH, no server configuration
- **Cons:** Slower for large file operations, not ideal for heavy writes
- **Best for:** Occasional file edits, running scripts, CLI access

### NFS (Optional, faster for heavy use)

If you need better performance for frequent file operations:

**On Widow (run once):**
```bash
# Install NFS server
sudo apt install nfs-kernel-server

# Export the project directory
echo "/home/pete/projects/News Intelligence 192.168.93.0/24(rw,sync,no_subtree_check)" | sudo tee -a /etc/exports
sudo exportfs -ra

# Verify
showmount -e localhost
```

**On your development machine:**
```bash
# Install NFS client
sudo apt install nfs-common

# Create mount point
mkdir -p ~/widow-news-intel

# Mount
sudo mount -t nfs 192.168.93.101:/home/pete/projects/News\ Intelligence ~/widow-news-intel

# Auto-mount on boot (add to /etc/fstab)
echo "192.168.93.101:/home/pete/projects/News Intelligence ~/widow-news-intel nfs rw,vers=4 0 0" | sudo tee -a /etc/fstab
```

---

## Troubleshooting

### SSHFS: Connection refused
```bash
# Verify SSH connection works
ssh widow "cd ~/projects/News\ Intelligence && pwd"

# Check if SSHFS is installed
which sshfs
# If not installed:
sudo apt install sshfs
```

### SSHFS: Permission denied
```bash
# The mount script uses allow_other flag
# If issues persist, check /etc/fuse.conf for user_allow_other
```

### NFS: Client cannot resolve hostname
```bash
# Add Widow to /etc/hosts if DNS not configured
echo "192.168.93.101 widow" | sudo tee -a /etc/hosts
```

### Stale mount point
```bash
# If mount fails because directory is not empty or stale
fusermount -u ~/widow-news-intel
# Or
umount -l ~/widow-news-intel  # Lazy unmount
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Your Development Machine (192.168.93.99)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ~/widow-news-intel  ← SSHFS Mount Point             │  │
│  │     ├── api/                                           │  │
│  │     ├── scripts/                                       │  │
│  │     ├── docs/                                          │  │
│  │     └── ...                                            │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │                                            │
│                 │ SSHFS (over SSH)                           │
│                 ▼                                            │
└─────────────────────────────────────────────────────────────┘
                         │
                         │ 192.168.93.0/24 Network
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Widow Server (192.168.93.101)                              │
├─────────────────────────────────────────────────────────────┤
│  /home/pete/projects/News Intelligence/                     │
│     ├── api/ (live database, processing)                    │
│     ├── scripts/                                            │
│     └── ...                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Recommended Workflow

### For Daily Development

**Primary: VS Code Remote SSH**
1. Open VS Code: `code --remote ssh-remote+widow`
2. Navigate to project or use Favorites
3. Edit, debug, run commands all on Widow

**Secondary: SSHFS for specific tasks**
- Running local scripts that need file access
- Using tools that expect local paths
- Backup/migration operations

### For One-Time Tasks

```bash
# Quick SSH into project directory
widow-project

# Or mount temporarily
widow-mount
cd ~/widow-news-intel
# ... do your work ...
widow-unmount