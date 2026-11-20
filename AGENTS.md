# Agent Guidance — News Intelligence

**How to work:** `.clinerules/ni-agent.md` (principles, vault + MemPalace + grep, Plan/Act).

**Anti-drift / repair:** `docs/OPERATING_PRINCIPLES.md` · `docs/NI_REPAIR_PLAN.md` · skill `ni-operating-principles` · `docs/monitor_alignment/CROSSWALK.md`.

**MCP & homelab:** `docs/AVAILABLE_SERVICES_AND_MCP.md` · global `~/Documents/Cline/Rules/00-connected-mcp-server-ids.md`.

**Code/migrations:** `.clinerules/workflow.md`.

**Product pipeline (RSS → reader):** `docs/GOLDEN_RSS_TO_READER.md` + skill `.clinerules/skills/ni-golden-trace/SKILL.md` — **required** for feed/brief/RSS fixes; no “done” without a golden `article_id` trace (Cursor rule: `.cursor/rules/ni-golden-trace-root-cause.mdc`).

**Database golden path:** `docs/GOLDEN_PATH_DATABASE.md` + `docs/SCHEMA_MISMATCH_REMEDIATION.md` + skill `ni-db-golden-path` — domain data in `{schema}.articles` / `{schema}.storylines`, not `public.*` stubs; suggestions in `public.storyline_article_suggestions` only.

**Runtime pipeline on Widow (ops):** `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` — refresh `./scripts/repomix_pack_ni.sh`, then `grep_repomix_output` / `rg` before opening large services.

## Key paths

| Area | Location |
|------|----------|
| API | `api/` |
| Frontend | `web/src/` |
| Migrations | `api/database/migrations/` |
| Deploy (Widow) | `./scripts/deploy_to_widow.sh` |
| Code pack (grep) | `./scripts/repomix_pack_ni.sh` → `repomix-output.xml` |

DB live: Widow `news_intel` via homelab **`postgres-mcp`** (not PopOS homelab Postgres).
