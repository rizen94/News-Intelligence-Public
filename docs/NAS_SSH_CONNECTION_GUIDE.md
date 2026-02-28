# NAS SSH Connection Guide

**Date**: December 16, 2024  
**Purpose**: Connect to NAS and check Docker containers

---

## 🔐 Connection Details

- **Host**: 192.168.93.100
- **SSH Port**: 9222
- **Username**: Admin
- **Password**: Pooter@STORAGE2024

---

## 🚀 Quick Connection

```bash
ssh -p 9222 Admin@192.168.93.100
```

Enter password when prompted: `Pooter@STORAGE2024`

---

## 📋 Check Docker Containers

Once connected to NAS, run:

### Check All Running Containers
```bash
docker ps
```

### Check PostgreSQL Containers
```bash
docker ps -a | grep postgres
docker ps --filter 'name=postgres'
```

### Check Container Status
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

---

## 🔧 PostgreSQL Container Operations

### If Container is Stopped
```bash
# Find container name
docker ps -a --filter 'name=postgres'

# Start container
docker start <container-name>
```

### Check PostgreSQL Logs
```bash
docker logs <postgres-container-name>
docker logs --tail 50 <postgres-container-name>
```

### Test PostgreSQL Connection
```bash
# Check if PostgreSQL is ready
docker exec <postgres-container-name> pg_isready -U postgres

# Connect to PostgreSQL
docker exec -it <postgres-container-name> psql -U postgres

# Check version
docker exec <postgres-container-name> psql -U postgres -c 'SELECT version();'

# List databases
docker exec <postgres-container-name> psql -U postgres -c '\l'

# Check if news_intelligence database exists
docker exec <postgres-container-name> psql -U postgres -c "SELECT datname FROM pg_database WHERE datname = 'news_intelligence';"

# Check if newsapp user exists
docker exec <postgres-container-name> psql -U postgres -c "SELECT usename FROM pg_user WHERE usename = 'newsapp';"
```

---

## 🛠️ Automated Check Script

A script is available to automate the check:

```bash
# Install sshpass (required for password authentication)
sudo apt-get install sshpass

# Run the check script
./scripts/check_nas_containers.sh
```

---

## 🔍 Troubleshooting

### SSH Connection Fails
- Verify NAS is accessible: `ping 192.168.93.100`
- Check port is open: `nc -zv 192.168.93.100 9222`
- Verify credentials are correct

### Container Not Found
- PostgreSQL container may not exist on NAS
- Need to create it using: `./scripts/setup_nas_database.sh`
- Or manually set up PostgreSQL on NAS

### Container Stopped
- Start with: `docker start <container-name>`
- Check logs: `docker logs <container-name>`
- Verify container configuration

---

*Use this guide to connect to NAS and verify PostgreSQL container status*

