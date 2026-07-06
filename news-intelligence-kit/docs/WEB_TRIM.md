# Intake SPA trim (kit)

The kit intake surface includes only:

| Page | Route |
|------|-------|
| Dashboard | `/:domain/dashboard` |
| Monitor | `/monitor` |
| Entities list/detail | `/:domain/investigate/entities` |
| Events | `/:domain/investigate/events`, `/events` |
| Articles | `/:domain/articles` |
| Storylines | `/:domain/storylines` |
| RSS | `/:domain/rss` |

## Apply patches before build

```bash
news-intelligence-kit/scripts/trim_web_for_kit.sh
cd web && npm run build
docker compose -f news-intelligence-kit/compose.yaml build intake-web
```

`trim_web_for_kit.sh` clears `FALLBACK_DOMAINS` in `domainHelper.ts` so the UI uses **registry_domains only**.

## Setup gate

`web/static/setup-gate.js` redirects to `/setup/` when `setup_complete` is false (injected by nginx).

## Dropped routes (v1)

Finance, Arcs, Hypotheses UI, SqlExplorer, Briefings editor, ML admin — use full NI repo if needed.

## Open in Agent links

Entity/event detail pages should deep-link to Open WebUI (`http://localhost:3001/`) with query context — wire in a future kit web patch if not present in parent build.
