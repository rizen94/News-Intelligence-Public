# Upgrade

1. **Backup:** `./scripts/backup_kit.sh`
2. **Pull new kit tree** (zip or git)
3. **Preserve** `data/`, `.env`, and `config/domains/*.yaml` (not `_examples/`)
4. **Run:** `./scripts/upgrade_kit.sh`

The upgrade script rebuilds images, runs `verify_kit.sh`, and applies any new migration files in `migrations/` manually if Postgres volume already exists (initdb scripts only run on fresh volumes).

## Schema updates on existing installs

For incremental SQL after first boot:

```bash
docker compose exec -T postgres psql -U newsapp -d news_intel -f /path/to/new_migration.sql
```

Kit tracks version in `automation_state.kit_schema_version`.
