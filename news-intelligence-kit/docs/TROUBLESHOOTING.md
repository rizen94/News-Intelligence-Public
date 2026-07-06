# Troubleshooting

## Setup UI cannot reach API

```bash
docker compose ps
docker compose logs api --tail 80
./scripts/repair.sh
```

Ensure intake-web proxies `/api/` to the `api` service (port 8000 inside the network).

## Ollama down / slow model pull

```bash
docker compose logs ollama
./scripts/pull_ollama_models.sh
```

On CPU-only hosts set `KIT_HARDWARE_TIER=minimal` and use smaller models.

## Postgres fails on WSL `/mnt/c`

Move the kit to `~/news-intelligence-kit`. Postgres volumes on `/mnt/*` are unreliable.

## Automation not ingesting RSS

1. Confirm setup completed: `curl localhost:8080/api/setup/status`
2. Run `./scripts/enable_automation.sh`
3. Check domains: `curl localhost:8080/api/system_monitoring/registry_domains`
4. Inspect logs: `docker compose logs api | grep -i collection`

## Empty domain list in UI

Complete setup or run headless provision. Kit clears politics/finance fallbacks — the registry is empty until you provision.

## Open WebUI tools fail

Tools call `http://api:8000` from inside the Compose network. On the host browser, use intake at `:8080` for API checks. Import tools per `scripts/import_owui_tools.sh`.

## Support bundle

```bash
./scripts/support_bundle.sh
```

Attach output when reporting issues.
