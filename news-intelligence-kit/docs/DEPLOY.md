# Deployment

## Architecture

Single-host Docker Compose stack:

- **postgres** — `news_intel` with squashed baseline + runtime domain provisioning
- **ollama** — local LLM
- **api** — NI API + kit routes (`main_kit:app`)
- **intake-web** — nginx serving trimmed React SPA + `/setup`
- **open-webui** — agent chat on port 3001

## Build context

Images build from the **parent** News Intelligence repository:

```bash
# From repo root
cd news-intelligence-kit
docker compose build
```

API Dockerfile copies `api/` and overlays `kit_api/`. Web Dockerfile copies `web/dist/` (build web first or use export script).

## Export distributable zip

From repo root:

```bash
cd web && npm run build   # optional: run trim_web_for_kit.sh first
cd ..
news-intelligence-kit/scripts/export_kit.sh
```

Produces `news-intelligence-kit.zip` without local `data/` secrets.

## Production-ish hardening

For a LAN deployment:

1. Change default passwords in `.env`
2. Set `NEWS_INTEL_ENV=production`
3. Put nginx/Caddy TLS in front of ports 8080 and 3001
4. Enable Open WebUI auth (`WEBUI_AUTH=true` in compose override)
5. Schedule `./scripts/backup_kit.sh` via cron

## Upgrades

See [UPGRADE.md](UPGRADE.md).

## MemPalace (optional)

Not included in default compose. To attach homelab MemPalace MCP, add a sidecar profile pointing at your existing stack — vault notes remain the primary agent memory in kit v1.
