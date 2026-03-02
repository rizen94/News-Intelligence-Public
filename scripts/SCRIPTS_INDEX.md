# Scripts Index

## Essential (daily use)

| Script | Purpose |
|--------|---------|
| `../start_system.sh` | Start all services |
| `../stop_system.sh` | Stop API and frontend |
| `setup_nas_ssh_tunnel.sh` | Establish SSH tunnel to NAS DB (localhost:5433); auto-run by start_system.sh |
| `verify_gpu.py` | GPU and environment verification (nvidia-smi, PyTorch, Ollama, sentence-transformers) |
| `resource_monitor.py` | Real-time GPU/RAM monitoring (run during pipeline) |
| `benchmark_inference.py` | LLM inference speed benchmark (requires Ollama) |
| `verify_connections.py` | Verify NAS DB, internet, Ollama, Redis from venv |
| `../status_system.sh` | Check service status |
| `rss_collection_with_health_check.sh` | Run RSS collection with API health check |
| `setup_rss_cron_with_health_check.sh` | Configure cron for RSS collection |
| `restart_api_with_db.sh` | Restart API server |
| `backup_database.sh` | Backup database |

## Widow (secondary machine / migration)

| Script | Purpose |
|--------|---------|
| `setup_widow_ssh.sh` | Add SSH config for Widow (192.168.93.101); enables `ssh widow` |
| `run_widow_updates.sh` | Run apt update & upgrade on Widow via SSH (from primary) |

## Maintenance

| Script | Purpose |
|--------|---------|
| `maintenance/daily_audit.sh` | Daily system audit |
| `maintenance/docker-manage.sh` | Docker management |
| `check_nas_health.sh` | NAS connection check |
| `monitor_nas_mount.sh` | Monitor NAS mount |

## Archived

Scripts in `archive/` are one-time setup, migrations, or deprecated. See subdirs: `v4_migrations`, `duplicate_production`, `one_time_setup`, `one_time_ops`, `deployment`.
