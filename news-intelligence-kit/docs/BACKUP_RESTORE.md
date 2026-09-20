# Backup and restore

## Backup

```bash
./scripts/backup_kit.sh
```

Creates `data/backups/kit_YYYYMMDD_HHMMSS/` with:

- `news_intel.sql` — Postgres dump
- `vault.tar.gz` — Obsidian vault
- `.env` and `config/domains/` copies

## Restore

```bash
./scripts/restore_kit.sh data/backups/kit_YYYYMMDD_HHMMSS
```

Stops stack, restores Postgres and vault, restarts services.

## Scheduled backups (optional)

Compose profile (runs `backup_kit.sh` every 24h by default):

```bash
docker compose -f compose.yaml -f compose.backup.yaml --profile backup up -d
```

Host cron alternative:

```cron
0 3 * * * cd /path/to/news-intelligence-kit && ./scripts/backup_kit.sh
```

## Last-resort reset

```bash
./scripts/reset_data.sh   # wipes Postgres + Ollama data; re-run setup
```

## Before major upgrade

Always run backup first. See [UPGRADE.md](UPGRADE.md).
