---
name: Documentation and external context
description: Use when answering questions about frameworks, libraries, project architecture, or ops—prefer in-repo docs first, then public docs or Context7 MCP if configured.
alwaysApply: false
---

# Documentation and context (private repo + public references)

## This workspace (no extra MCP required for the main app)

The primary **internal codebase** is the **opened workspace** (`News Intelligence`). Agent mode should use **read/search tools** and **`.continue/rules`** before guessing.

Authoritative **in-repo** documentation (read these paths when relevant):

- `AGENTS.md` — terminology, API conventions, DB rules, entry points
- `docs/CODEBASE_MAP.md` — navigation
- `docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md` — pipeline order
- `docs/CODING_STYLE_GUIDE.md` — Python + TS conventions
- `docs/PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md` — ingest / phase contracts
- `docs/CODE_REVIEW_AND_RUN_CAVEATS.md` — run/ops caveats
- `docs/WEB_API_CONNECTIONS.md` — frontend ↔ API wiring
- `web/FRONTEND_STYLE_GUIDE.md` — UI/logging conventions

For **framework and library API** questions (not project-specific), prefer official public docs—or **Context7 MCP** if you have it installed in Continue—so answers match current versions.

## Public documentation (common stack in this project)

- **React:** https://react.dev/reference/react  
- **TypeScript:** https://www.typescriptlang.org/docs/  
- **Vite:** https://vite.dev/guide/  
- **MUI v5:** https://mui.com/material-ui/getting-started/  
- **FastAPI:** https://fastapi.tiangolo.com/  
- **Pydantic v2:** https://docs.pydantic.dev/latest/  
- **PostgreSQL:** https://www.postgresql.org/docs/current/  
- **psycopg2:** https://www.psycopg.org/docs/  

Cite or summarize from docs when explaining non-obvious API behavior.

## When Continue’s docs suggest “internal” or cross-repo setup

Use **custom MCP** or **custom code RAG** only if you need:

- A **second private repository** or monorepo slice **outside** this workspace, or  
- **Internal wikis / ticketing** (Confluence, Notion, private HTTP) that are not in `docs/`.

For wikis that are only URLs (no MCP yet), add a short rule with those links—or a tiny MCP server that fetches allowed internal URLs.

## Optional: Context7 MCP

If **Context7** is configured in Continue, use it for “what’s the current syntax for …?” style questions against **public** library docs instead of relying on stale training data.
