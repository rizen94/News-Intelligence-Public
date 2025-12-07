# Install Startup Service for Auto-Start on Reboot

This guide shows how to install the systemd service that automatically starts Redis, API server, and frontend on system reboot.

## Prerequisites

- Docker installed and running
- Node.js and npm installed
- Python 3 installed
- User-level systemd support (most modern Linux distributions)

## Installation Steps

### 1. Copy Service File to User Systemd Directory

```bash
cd "/home/pete/Documents/projects/Projects/News Intelligence"
mkdir -p ~/.config/systemd/user
cp news-intelligence-system.service ~/.config/systemd/user/
```

### 2. Reload Systemd and Enable Service

```bash
systemctl --user daemon-reload
systemctl --user enable news-intelligence-system
```

### 3. Enable Lingering (Allow Service to Run Without Login)

```bash
sudo loginctl enable-linger $USER
```

### 4. Test the Service

Start the service manually to test:

```bash
systemctl --user start news-intelligence-system
```

Check the status:

```bash
systemctl --user status news-intelligence-system
```

View logs:

```bash
journalctl --user -u news-intelligence-system -f
```

## Service Management

### Start Service
```bash
systemctl --user start news-intelligence-system
```

### Stop Service
```bash
systemctl --user stop news-intelligence-system
```

### Restart Service
```bash
systemctl --user restart news-intelligence-system
```

### Check Status
```bash
systemctl --user status news-intelligence-system
```

### View Logs
```bash
journalctl --user -u news-intelligence-system -f
```

### Disable Auto-Start
```bash
systemctl --user disable news-intelligence-system
```

## What Gets Started

The service automatically starts:

1. **Redis** - Cache/database (via Docker container `news-intelligence-redis`)
2. **API Server** - FastAPI backend on port 8000
3. **Frontend** - React development server on port 3000

## Logs

- **Service logs**: `journalctl --user -u news-intelligence-system`
- **API logs**: `~/Documents/projects/Projects/News Intelligence/logs/api_server.log`
- **Frontend logs**: `~/Documents/projects/Projects/News Intelligence/logs/frontend.log`
- **Startup log**: `~/Documents/projects/Projects/News Intelligence/logs/startup.log`

## Troubleshooting

### Service Fails to Start

1. Check Docker is running:
   ```bash
   docker info
   ```

2. Check service logs:
   ```bash
   journalctl --user -u news-intelligence-system -n 50
   ```

3. Verify paths in service file match your system

4. Check permissions:
   ```bash
   ls -la start.sh
   chmod +x start.sh
   ```

### Service Starts But Services Don't Respond

1. Check if processes are running:
   ```bash
   ps aux | grep -E "(uvicorn|react|redis)"
   ```

2. Check individual service logs:
   ```bash
   tail -f logs/api_server.log
   tail -f logs/frontend.log
   ```

3. Manually start Redis:
   ```bash
   docker start news-intelligence-redis
   ```

## Verification After Reboot

After a system reboot, verify all services are running:

```bash
# Check Redis
docker exec news-intelligence-redis redis-cli ping

# Check API
curl http://localhost:8000/api/v4/system-monitoring/status

# Check Frontend
curl http://localhost:3000
```

## Uninstalling

To remove the service:

```bash
systemctl --user disable news-intelligence-system
systemctl --user stop news-intelligence-system
rm ~/.config/systemd/user/news-intelligence-system.service
systemctl --user daemon-reload
```

