# Remote Cline/VS Code Access via code-server

## Overview

A remote VS Code-like coding environment is now available via the internet, allowing you to code on your local machine from any personal device. This is exposed through Caddy reverse proxy with password protection.

## Access URL

```
https://cline-local-agent.duckdns.org
```

## Authentication

| Credential | Value |
|------------|-------|
| Password | `e17024f3147e557a53ebbd6c` |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERNET / YOUR DEVICE                    │
│                    (phone, tablet, etc.)                    │
└──────────────────────────────────┬──────────────────────────┘
                                   │
                                   ▼
                    https://cline-local-agent.duckdns.org
                                   │
                                   ▼
                    ┌───────────────────────┐
                    │    Caddy (Docker)     │
                    │  (TLS termination)    │
                    │  homelab-ai-stack     │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   code-server         │
                    │   (port 12345)        │
                    │   systemd service     │
                    │   code-server@pete    │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Your VS Code        │
                    │   workspace & files   │
                    │   /home/pete          │
                    └───────────────────────┘
```

## Configuration Files

### 1. code-server config
Location: `/home/pete/.config/code-server/config.yaml`
```yaml
bind-addr: 127.0.0.1:12345
auth: password
password: e17024f3147e557a53ebbd6c
cert: false
```

### 2. systemd service
Location: `/etc/systemd/system/code-server@pete.service`
```ini
[Unit]
Description=code-server for Pete
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pete
WorkingDirectory=/home/pete
ExecStart=/usr/bin/code-server --config /home/pete/.config/code-server/config.yaml
Restart=always
RestartSec=5
Environment=HOME=/home/pete

[Install]
WantedBy=default.target
```

### 3. Caddy configuration
Location: `/home/pete/Documents/projects/HomeLab-AI-Stack/ai-lab/config/caddy/Caddyfile`
```caddyfile
cline-local-agent.duckdns.org {
    encode gzip
    reverse_proxy host.docker.internal:12345
}
```

## Service Management

```bash
# Check status
sudo systemctl status code-server@pete

# Restart service
sudo systemctl restart code-server@pete

# View logs
sudo journalctl -u code-server@pete -f

# Stop service
sudo systemctl stop code-server@pete

# Start service
sudo systemctl start code-server@pete
```

## Caddy Management

```bash
# Reload Caddy configuration (if modified)
# Note: Caddy runs in Docker, configuration is auto-reloaded when file changes
docker logs -f ai-lab-caddy
```

## Security Notes

1. **Password protection** - code-server requires password authentication (configured in config.yaml)
2. **TLS encryption** - Caddy automatically provides HTTPS via Let's Encrypt
3. **Local binding** - code-server binds to 127.0.0.1 only, not exposed directly to network
4. **Reverse proxy** - All traffic goes through Caddy, which handles TLS termination

## Features

- Full VS Code interface in your browser
- Access to your local files at `/home/pete`
- Terminal access within the browser
- Extensions support (via code-server extension marketplace)
- Works on any device with a modern browser

## Troubleshooting

### Service not responding
```bash
sudo systemctl status code-server@pete
sudo journalctl -u code-server@pete --no-pager -n 50
```

### Caddy not routing
```bash
docker logs ai-lab-caddy --tail 50
```

### Port already in use
Check if port 12345 is available:
```bash
ss -tlnp | grep 12345
```

## Updating the Password

To change the password, edit `/home/pete/.config/code-server/config.yaml`:
```bash
nano /home/pete/.config/code-server/config.yaml
```
Then restart:
```bash
sudo systemctl restart code-server@pete
```

---

**Setup Date:** May 28, 2026  
**Purpose:** Remote Cline/VS Code access for coding from personal devices