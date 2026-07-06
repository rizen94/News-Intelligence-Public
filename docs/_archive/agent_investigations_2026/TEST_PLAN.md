# News Intelligence System Test Plan

## Overview
This test plan outlines procedures to verify the News Intelligence System is functioning correctly on the Widow development environment. The system uses repomix for code packaging and mempalace MCP for memory operations, with code changes rsynced to the Widow server for execution.

## Preconditions
- Development environment: PopOS local machine
- Deployment target: Widow server (192.168.93.101)
- Code synchronization: Changes made locally are rsynced to Widow
- Services: API services running on Widow via systemd

## Test Objectives
1. Verify development environment setup
2. Confirm code synchronization mechanism works
3. Validate system services are running on Widow
4. Check API endpoints are responsive
5. Verify database connectivity
6. Test mempalace MCP integration
7. Confirm basic system functionality

## Test Procedures

### 1. Environment Verification
```bash
# Verify local development environment
hostname
pwd | grep "News Intelligence"

# Verify Widow connectivity
widow-project hostname
widow-project hostname -I
```

### 2. Code Synchronization Verification
```bash
# Make a test change locally
echo "# Test change $(date)" > /tmp/test_sync.txt
rsync -avz /tmp/test_sync.txt widow:/home/pete/Documents/projects/News Intelligence/test_sync.txt

# Verify on Widow
widow-project "ls -la /home/pete/Documents/projects/News Intelligence/test_sync.txt"
widow-project "cat /home/pete/Documents/projects/News Intelligence/test_sync.txt"

# Cleanup
widow-project "rm /home/pete/Documents/projects/News Intelligence/test_sync.txt"
rm /tmp/test_sync.txt
```

### 3. Service Status Verification
```bash
widow-project "systemctl status news-intelligence-api-public.service"
widow-project "systemctl status automation-manager.service"
widow-project "systemctl status embeddings-worker-service.service"
widow-project "systemctl status entity-resolution-service.service"
widow-project "systemctl status storyline-service.service"
```

### 4. API Health Checks
```bash
# Basic health endpoint
widow-project "curl -s http://localhost:8000/api/health | jq ."

# Public demo config
widow-project "curl -s http://localhost:8000/api/public/demo_config | jq ."

# System monitoring
widow-project "curl -s http://localhost:8000/api/system_monitoring/health | jq ."

# Domain-specific API (example: AI domain)
widow-project "curl -s 'http://localhost:8000/api/domains/artificial-intelligence/articles?limit=1' | jq '. | {count: .count, sample: .results[0].title if .results else \"none\"}'"
```

### 5. Database Connectivity
```bash
widow-project "python3 -c "
import sys
sys.path.append('/home/pete/Documents/projects/News Intelligence/api/shared')
from database.connection import get_db_connection_context
try:
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT version();')
            version = cur.fetchone()
            print('✓ Database connected:', version[0][:50])
except Exception as e:
    print('✗ Database connection failed:', str(e))
"
```

### 6. MemPalace MCP Integration Test
```bash
# Test mempalace MCP connection via Cursor tools
# This would be done through the MCP interface in Cursor
# For verification, we can check if the MCP server is accessible
widow-project "docker ps | grep mempalace"
```

### 7. Repomix Integration Test
```bash
# Test repomix packaging
repomix --output /tmp/test_repomix.xml --style xml --no-logs --no-directory-structure api/shared/

# Verify output was created
ls -lh /tmp/test_repomix.xml
head -5 /tmp/test_repomix.xml

# Cleanup
rm /tmp/test_repomix.xml
```

## Expected Results

### Environment Verification
- Local hostname shows PopOS machine
- Current directory is News Intelligence project
- Widow connectivity shows 192.168.93.101

### Code Synchronization
- Test file successfully rsynced to Widow
- File contents match on both systems
- Cleanup successful on both systems

### Service Status
- All key services show "active (running)" status
- No failed services in systemctl output

### API Health Checks
- Health endpoint returns {"status": "ok"} or similar
- Public demo config returns valid JSON with configuration
- System monitoring shows healthy status
- Domain API returns articles with count and sample title

### Database Connectivity
- Successful connection to news_intel database
- Version information returned for PostgreSQL

### MemPalace MCP Integration
- MemPalace MCP container shows as running
- MCP tools accessible through Cursor interface

### Repomix Integration
- Repomix successfully creates output file
- Output contains expected XML structure
- File size indicates proper packaging occurred

## Notes
- Replace service names with actual service names if different
- Adjust ports if services run on non-standard ports
- Some tests may require sudo privileges on Widow
- Ensure proper SSH key setup for widow-project command
- Test during off-peak hours to avoid interfering with ongoing processes