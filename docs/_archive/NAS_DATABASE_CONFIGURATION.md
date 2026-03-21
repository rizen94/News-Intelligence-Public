# NAS Database Configuration - Final Status

## ✅ Current Status: **NAS IS THE MAIN DATABASE**

### Configuration Summary

1. **System Configuration:**
   - `start_system.sh`: Defaults to NAS (<NAS_HOST_IP>:5432)
   - Blocks localhost connections unless using SSH tunnel (localhost:5433)
   - Validates NAS connectivity before starting services

2. **Database Manager:**
   - `api/config/database.py`: Requires `DB_HOST` environment variable
   - Blocks localhost unless `ALLOW_LOCAL_DB=true`
   - Enforces NAS database requirement

3. **Network Setup:**
   - Direct NAS connection: BLOCKED by firewall (<NAS_HOST_IP>:5432)
   - SSH tunnel: REQUIRED (localhost:5433 -> NAS:5432)
   - Tunnel port: 5433 (to avoid conflict with local PostgreSQL on 5432)

### How to Use NAS Database

#### Option 1: SSH Tunnel (Recommended)
```bash
# Set environment variables
export DB_HOST=localhost
export DB_PORT=5433

# Or update configs/.env
DB_HOST=localhost
DB_PORT=5433
```

#### Option 2: Direct Connection (If firewall allows)
```bash
export DB_HOST=<NAS_HOST_IP>
export DB_PORT=5432
```

### Setting Up SSH Tunnel

Run the setup script:
```bash
./scripts/setup_nas_ssh_tunnel.sh
```

Or manually:
```bash
ssh -L 5433:localhost:5432 -N -f -p 9222 Admin@<NAS_HOST_IP>
```

### Verification

To verify you're connected to NAS:
```python
import psycopg2
conn = psycopg2.connect(host='localhost', port=5433, ...)
cursor = conn.cursor()
cursor.execute('SELECT version();')
version = cursor.fetchone()[0]
# Should contain 'aarch64' (ARM architecture = NAS)
```

### Migration Status

✅ **COMPLETE**: 638 records migrated to NAS
- RSS Feeds: 52 records
- Articles: 586 records

### Important Notes

1. **configs/.env**: Currently points to local database (`news-system-postgres-local`)
   - **ACTION REQUIRED**: Update to use `localhost:5433` for NAS via SSH tunnel

2. **SSH Tunnel**: Must be running before starting the application
   - Check: `ps aux | grep "ssh.*5433.*<NAS_HOST_IP>"`
   - Auto-setup: `start_system.sh` will attempt to create tunnel if missing

3. **Local PostgreSQL**: Still running on port 5432
   - This is OK - tunnel uses port 5433
   - Local DB is blocked by configuration

### Next Steps

1. Update `configs/.env`:
   ```bash
   DB_HOST=localhost
   DB_PORT=5433
   ```

2. Verify SSH tunnel is persistent (or set up as systemd service)

3. Test application startup:
   ```bash
   ./start_system.sh
   ```

4. Verify application connects to NAS:
   - Check logs for "Connected to NAS database (ARM)"
   - Verify data appears in application
