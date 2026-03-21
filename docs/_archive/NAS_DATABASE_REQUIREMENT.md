# NAS Database Requirement - System Policy

## 🚨 CRITICAL: NAS Database is REQUIRED

This system **MUST** use the NAS database for all data storage. Local storage is **BLOCKED** by default due to insufficient disk space.

---

## 📋 Policy

### ✅ REQUIRED
- **Database Host**: `<NAS_HOST_IP>` (NAS)
- **Storage Location**: Remote NAS storage only
- **Default Behavior**: System fails to start if NAS is not available

### ❌ BLOCKED
- Local database connections (`localhost`, `127.0.0.1`)
- Local PostgreSQL instances
- Local data storage (unless explicitly permitted)

### ⚠️ EMERGENCY OVERRIDE
Local database can only be used with explicit permission:
```bash
export ALLOW_LOCAL_DB=true
export DB_HOST=localhost
```

**WARNING**: This should only be used for emergency maintenance. Local storage will fill up quickly.

---

## 🔧 Configuration

### Default Configuration (NAS Required)

```bash
export DB_HOST=<NAS_HOST_IP>
export DB_PORT=5432
export DB_NAME=news_intelligence
export DB_USER=newsapp
export DB_PASSWORD=newsapp_password
```

### NAS Credentials

- **NAS Host**: `<NAS_HOST_IP>`
- **NAS Share**: `public`
- **NAS User**: `Admin`
- **NAS Password**: `Pooter@STORAGE2024`
- **NAS Workgroup**: `LAKEHOUSE`
- **NAS Mount Path**: `/mnt/nas`

---

## 🛡️ Safeguards

### 1. Database Configuration (`api/config/database.py`)
- **Blocks** localhost connections unless `ALLOW_LOCAL_DB=true`
- **Requires** `DB_HOST` environment variable
- **Fails** with clear error message if localhost detected

### 2. Startup Script (`start_system.sh`)
- **Validates** NAS database is accessible before starting
- **Blocks** localhost connections unless `ALLOW_LOCAL_DB=true`
- **Exits** with error if NAS is unreachable

### 3. Runtime Checks
- Database connection manager validates host
- Application fails fast if wrong database detected

---

## 🚀 Usage

### Normal Operation (NAS Required)

```bash
# Default - uses NAS automatically
./start_system.sh
```

### Emergency Local Override (NOT RECOMMENDED)

```bash
# Only for emergency maintenance
export ALLOW_LOCAL_DB=true
export DB_HOST=localhost
./start_system.sh
```

**⚠️ WARNING**: Local storage will fill up. Use only for emergency maintenance.

---

## 🔍 Verification

### Check Current Database Host

```bash
echo $DB_HOST
```

Should show: `<NAS_HOST_IP>`

### Test NAS Connection

```bash
nc -zv <NAS_HOST_IP> 5432
```

Should show: `Connection to <NAS_HOST_IP> 5432 port [tcp/postgresql] succeeded!`

### Verify Database Location

```python
from api.config.database import get_db_config
config = get_db_config()
print(f"Database Host: {config['host']}")
```

Should show: `Database Host: <NAS_HOST_IP>`

---

## 📊 Why NAS is Required

1. **Storage Capacity**: Local disk has insufficient space (97.4% used)
2. **Data Persistence**: NAS provides reliable network storage
3. **Backup Strategy**: NAS storage is backed up and redundant
4. **System Stability**: Prevents disk space issues from crashing system

---

## 🚨 Error Messages

### If Localhost Detected

```
[ERROR] Local database connection is BLOCKED.
[ERROR] System requires NAS database (<NAS_HOST_IP>) for storage.
[ERROR] Local storage has insufficient space.
[INFO] To override (EMERGENCY ONLY), set: ALLOW_LOCAL_DB=true
```

### If NAS Unreachable

```
[ERROR] Cannot connect to NAS database at <NAS_HOST_IP>:5432
[ERROR] Please ensure NAS is accessible and PostgreSQL is running.
```

### If DB_HOST Not Set

```
ValueError: DB_HOST environment variable is REQUIRED.
System must use NAS database (<NAS_HOST_IP>).
Local storage is not permitted due to insufficient space.
```

---

## 🔄 Migration Checklist

After migrating to NAS database:

- [x] ✅ Database configuration updated to require NAS
- [x] ✅ Startup script validates NAS connection
- [x] ✅ Localhost connections blocked by default
- [x] ✅ Emergency override available (with warning)
- [x] ✅ Documentation updated
- [ ] ⬜ Verify all data migrated successfully
- [ ] ⬜ Test system with NAS database
- [ ] ⬜ Remove local PostgreSQL (if no longer needed)
- [ ] ⬜ Update all documentation references

---

## 📝 Maintenance Notes

### When to Use Local Override

**ONLY** in these emergency situations:
1. NAS hardware failure (temporary)
2. Network connectivity issues (diagnostic)
3. Database migration/backup operations
4. Development/testing (with explicit permission)

### After Using Local Override

1. **Immediately** migrate data back to NAS
2. **Remove** `ALLOW_LOCAL_DB=true` flag
3. **Verify** system is using NAS again
4. **Document** why local override was needed

---

## 🔗 Related Files

- `api/config/database.py` - Database configuration with NAS requirement
- `start_system.sh` - Startup script with NAS validation
- `configs/consolidated/env-backup` - NAS credentials backup
- `.env.nas` - NAS configuration template

---

**Last Updated**: December 2025  
**Policy Version**: 1.0  
**Status**: ACTIVE - NAS Database Required

