# v12 web UI strip (2026-08-16)

Operator-facing SPA cleanup after MUST+THIN cutover. Routes still use `/storylines/*` for API/compat; labels say **Episodes**.

## Removed / redirected

| Surface | Change |
|---------|--------|
| Nav **Briefings** | Replaced with **News stories** → `/editor` |
| `/briefings`, `/report` | Redirect → `/editor` |
| Nav **Embedding catch-up** / discovery | Removed; `/storylines/discovery` redirects to episode list |
| **Discover storylines** button | Removed (discovery phase retired) |
| **Automation settings** dialog on episode detail | Removed (bag absorb / automation UI retired) |
| Protein job labels | Renamed to Analysis jobs |

## Renamed copy

- Storylines → Episodes (nav, list page, empty state, stats)
- Monitor: retired phase keys labeled; `storyline_assembly` → episode assembly
- Arc chronicle / research subject: protein → episode wording
- App boot log version → `12.0.0`

## Kept (intentionally)

- URL path `/storylines` (backend + bookmarks)
- Review queue, suggestions (HITL)
- Arc reports, editorial modals
- LAST bucket (Edition SPA) still deferred

## Deploy

Rebuilt with `npm run build:bundle`; synced to Widow:

- `/var/www/news-intelligence/web/dist` (nginx root)
- `/opt/news-intelligence/web/dist` (mirror)

API also exposes `membership_source` on storyline detail (`eel` | `storyline_articles`).

Follow-ups done 2026-08-16 afternoon: closed_thin queues, episode copy, Monitor retired hide, `_archived` dead pages.
