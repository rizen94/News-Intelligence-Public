# Scripts Index

## Essential

| Script | Purpose |
|--------|---------|
| `../start_system.sh` | Start all services (manual) |
| `../start-news-intelligence.sh` | Same as above; symlink from `~/bin` to run from anywhere (see script header) |
| `../stop_system.sh` | Stop API and frontend |
| `../restart_system.sh` | Stop then start (e.g. after changing .env) |
| `../status_system.sh` | Check service status |
| `archive_logs_to_nas.sh` | Copy old log files to NAS and trim local (run on Widow; keep disk clean) |
| `export_cold_data_to_nas.sh` | Export old articles/contexts to NAS (optional prune); see docs/NAS_LEGACY_AND_STORAGE.md |
| `setup_autostart.sh` | Enable auto-start on boot (systemd user services) |
| `setup_nas_ssh_tunnel.sh` | SSH tunnel to NAS (rollback only) |
| `restart_api_with_db.sh` | Restart API |
| `db_backup.sh` | DB backup (run on Widow) |

## Widow / secondary

| Script | Purpose |
|--------|---------|
| `setup_widow_ssh.sh` | SSH config for Widow |
| `deploy_to_widow.sh` | Deploy code to Widow |
| `setup_widow_app.sh` | Setup on Widow (venv, systemd) |
| `run_secondary_worker.py` | RSS daemon (Widow) |
| `configure_widow_no_sleep.sh` | Keep server on full time (no suspend/hibernate/power-saver) — run on server |
| `run_widow_updates.sh` | apt update on Widow |

## Migrations (API)

| Script | Purpose |
|--------|---------|
| `api/scripts/run_migrations_140_to_152.py` | Run migrations 140–154 (orchestration, intelligence, context-centric, watch patterns). From repo root: `PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_140_to_152.py` |
| `api/scripts/run_migrations_155_to_160.py` | Run migrations 155–161 (quality feedback, cross-domain, anomaly, claim merges, editorial docs, commodity feeds, processed_documents, automation_run_history). From repo root: `PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_155_to_160.py` |

## Utilities

| Script | Purpose |
|--------|---------|
| `verify_gpu.py` | GPU/ML verification |
| `verify_connections.py` | DB, Ollama, Redis check |
| `rss_collection_with_health_check.sh` | RSS + health check (used by cron) |
| `run_last_24h_report.sh` | Run last-24h activity report (uses .venv-report) |
| `setup_rss_cron_with_health_check.sh` | Install RSS cron (6/18) with quoted paths |
| `setup_morning_data_pipeline.sh` | Install morning pipeline cron (4/5/6 AM) with quoted paths |
| `setup_log_archive_cron.sh` | Install log-archive-to-NAS cron (6/18) with quoted paths |
| `setup_log_cleanup_cron.sh` | Install pipeline_trace.log cleanup (2 AM) with quoted path |
| `backup_database.sh` | DB backup |

## Archived

`scripts/archive/` — legacy NAS scripts, one-time migrations, deprecated.
