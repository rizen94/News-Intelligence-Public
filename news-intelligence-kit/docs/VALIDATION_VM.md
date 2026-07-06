# Validation procedure (fresh VM)

Use this checklist on a clean Linux VM or WSL instance before shipping a kit release.

## 1. Clean install

```bash
unzip news-intelligence-kit.zip
cd news-intelligence-kit
./install.sh
./scripts/smoke_test.sh
```

## 2. Setup UI path

1. Open http://localhost:8080/setup/
2. Enter interests: `sports, entertainment, pop culture`
3. Accept proposed domains and apply
4. Confirm redirect to dashboard after setup

## 3. Headless path (optional)

```bash
SMOKE_PROVISION=1 ./scripts/smoke_test.sh
# or
docker compose exec api python3 /app/kit/scripts/provision_from_spec.py /app/kit/config/setup/smoke_domains.json
./scripts/enable_automation.sh
```

## 4. Ingest smoke

```bash
./scripts/enable_automation.sh
sleep 120
curl -s "http://localhost:8080/api/sports/articles?limit=5" | head
curl -s "http://localhost:8080/api/system_monitoring/registry_domains" | head
```

## 5. Agent + vault

1. Open http://localhost:3001/
2. Ask agent to investigate a topic
3. Confirm `data/vault/threads/` receives a new markdown file

## 6. Export / reinstall

```bash
./scripts/backup_kit.sh
# Fresh VM: install again, restore backup, verify_kit.sh
```

## Pass criteria

- [ ] `verify_kit.sh` PASS
- [ ] Two custom domains in registry (sports + entertainment)
- [ ] At least one RSS article ingested per domain within 30 min
- [ ] Vault note written from agent or `/api/agent/investigate`
- [ ] Backup restore returns same domain count
