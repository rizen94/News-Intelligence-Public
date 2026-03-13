# News Intelligence — Architecture & Operations

**Version:** v5.0 (stable)  
**Last updated:** 2026-03-01

---

## Architecture Overview

Three-machine setup:

| Machine | IP | Role |
|---------|-----|------|
| **Primary** | 192.168.93.99 | API, ML, Ollama, Redis, Frontend |
| **Widow** | 192.168.93.101 | PostgreSQL, RSS worker, DB backups |
| **NAS** | 192.168.93.100 | Storage only (no PostgreSQL) |

### Data Flow

- **Primary** runs the FastAPI app, connects to Widow’s database over LAN
- **Widow** runs PostgreSQL and the RSS collector (systemd), backs up to local (or NAS if mounted)
- **NAS** is used for archives/backups; no application logic

---

## Quick Start

```bash
./start_system.sh    # Start API, frontend, Redis
./status_system.sh   # Check all services
./stop_system.sh     # Stop API and frontend (keeps DB/Redis)
```

**URLs**

- Frontend: http://localhost:3000
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v4/system_monitoring/health

---

## Database Configuration

**Primary config (Widow):**

- Host: 192.168.93.101
- Port: 5432
- Database: news_intel
- User: newsapp
- Password: in `.db_password_widow` or `.env` as `DB_PASSWORD`

**Rollback to NAS (if needed):**

1. Start PostgreSQL on NAS (Package Center or `systemctl start postgresql`)
2. In `.env`: `DB_HOST=localhost`, `DB_PORT=5433`, `DB_NAME=news_intelligence`, `DB_PASSWORD=newsapp_password`
3. Run `./scripts/setup_nas_ssh_tunnel.sh`
4. Restart app

---

## Widow (Secondary)

**Services**

- PostgreSQL 16 (system service)
- RSS worker: `newsplatform-secondary.service` (every 10 min)
- Backups: cron at 03:00 daily, 04:00 Sun weekly

**SSH**

```bash
ssh widow   # or ssh pete@192.168.93.101
```

**Common commands**

```bash
# On Widow
sudo systemctl status newsplatform-secondary
sudo systemctl status postgresql
./scripts/db_backup.sh   # Manual backup
```

---

## Key Scripts

| Script | Purpose |
|--------|---------|
| `start_system.sh` | Start all services |
| `stop_system.sh` | Stop API and frontend |
| `status_system.sh` | Status of all components |
| `scripts/deploy_to_widow.sh` | Deploy code to Widow |
| `scripts/configure_widow_no_sleep.sh` | Disable Widow sleep (run on Widow) |
| `scripts/decommission_nas_postgresql.sh` | Stop NAS PostgreSQL |

---

## Troubleshooting

**DB connection fails**

- Confirm Widow is on (ping 192.168.93.101)
- If Widow sleeps: run `scripts/configure_widow_no_sleep.sh` on Widow

**API won’t start**

- Check `.env` has `DB_PASSWORD` or `.db_password_widow` exists
- Confirm DB: `pg_isready -h 192.168.93.101 -p 5432 -U newsapp`

**Widow RSS worker stopped**

```bash
ssh widow "sudo systemctl restart newsplatform-secondary"
```
