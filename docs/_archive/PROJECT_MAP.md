# News Intelligence — Project Map

Quick reference for AI/agent context. Update as the project evolves.

**Agent guidance:** See `AGENTS.md` for terminology and coding standards.

## Entry points

| Role | Path |
|------|------|
| API | `api/main_v4.py` |
| Frontend | `web/src/App.tsx` |
| API client | `web/src/services/api/` (articles, watchlist) + `apiService.ts` |
| Domain routing | `web/src/components/shared/DomainLayout/DomainLayout.tsx` |

## Domain structure

- **Domains:** politics, finance, science-tech (shared schemas)
- **Per-domain:** articles, storylines, topics, rss_feeds, events
- **Global:** watchlist, monitoring, system_monitoring

## Key flows

1. **Article:** RSS → processing → storyline linking → event extraction
2. **Storyline:** create → add articles → analyze → timeline → watchlist
3. **Events (v5):** extract → deduplicate → story continuation → alerts

## File layout (post-shrink)

| Area | Location |
|------|----------|
| API routes | `api/domains/*/routes/` (consolidated per domain) |
| Services | `api/services/`, `api/domains/*/services/` |
| Frontend pages | `web/src/pages/` |
| API modules | `web/src/services/api/` (articles, watchlist, …) |

## Planned: Election Tracker (future)

Expanded election tracker for politics domain: maps, election updates, politician profiles. To develop later.

---

## Router imports (main_v4.py)

- news_aggregation
- content_analysis
- storyline_management
- intelligence_hub
- finance
- user_management
- system_monitoring
- compatibility
