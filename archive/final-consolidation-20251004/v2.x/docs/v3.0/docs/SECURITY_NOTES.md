# Security Notes for v3.0

## Database Password Security

**CRITICAL**: Update all database passwords when moving to v3.0

### Current Weak Passwords
- `newsapp123` - Used in database configuration
- `newsapp_password` - Used in ML worker (incorrect)

### Required Actions for v3.0
1. **Generate Strong Passwords**: Use cryptographically secure passwords (minimum 16 characters, mixed case, numbers, symbols)
2. **Update All Configurations**:
   - `api/config/database.py`
   - `api/scripts/ml_worker.py`
   - `api/scripts/automated_collection.py`
   - Docker environment variables
   - All database connection strings

3. **Implement Password Management**:
   - Use environment variables for all passwords
   - Never hardcode passwords in source code
   - Use secrets management for production

4. **Security Best Practices**:
   - Rotate passwords regularly
   - Use different passwords for different environments
   - Implement proper access controls
   - Audit database access logs

### Files Requiring Password Updates
- `api/config/database.py` - Main database config
- `api/scripts/ml_worker.py` - ML processing worker
- `api/scripts/automated_collection.py` - RSS collection
- `docker-compose.backend.yml` - Docker environment
- All database initialization scripts

**Priority**: HIGH - Security vulnerability
**Timeline**: Before v3.0 production release
