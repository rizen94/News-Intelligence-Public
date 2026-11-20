# Cline baseline (sustainable)

Thin **rules** + **skills** + **hooks**. Workflows deprecated.

## Workspace

`~/Documents/projects/news_intelligence`

## Always-on (workspace)

- `ni-agent.md` (shared)
- `workflow.md`

## Mode-specific (enable in Cline per mode)

| Cline mode | Also enable |
|------------|-------------|
| **Plan** | `ni-agent-plan.md` |
| **Act** | `ni-agent-act.md` |

Hooks inject **`NI_CLINE_MODE: act|plan`** when the task/prompt includes `CLINE_ACT`, `act mode`, `deploy authorized`, etc. Prefer **new task** after switching modes.

## Global

- **`00-connected-mcp-server-ids.md`** only

Retired globals live in `~/Documents/Cline/Rules/_retired/` (not loaded).

## Skills (invoke or auto-match)

`ni-golden-trace` · `ni-operating-principles` · `ni-pipeline-debug` · `ni-repomix-grep` · `ni-verify-change` · `ni-migrations` · `ni-plan-handoff` · `ni-ship-widow` · `ni-postgres` · `ni-graphify` · `ni-db-code` · `mempalace-tools` · `ni-serena-symbols`

Policy: `docs/OPERATING_PRINCIPLES.md` · repair: `docs/NI_REPAIR_PLAN.md` · MCP map: `docs/AVAILABLE_SERVICES_AND_MCP.md`

Product closure doc: `docs/GOLDEN_RSS_TO_READER.md`

Index: `.clinerules/README.md`

## Hooks

`.clinerules/hooks/` — TaskStart, PreToolUse, UserPromptSubmit (Features → Hooks on)

## Models

Plan `lab-backbone-reason:latest` · Act `lab-backbone:latest` · `useAutoCondense` **false**

## MCP (coding profile)

Sync: `MCP_STACK_CANON=.../mcp-stack.coding.json ./scripts/sync-agent-mcp.sh`

Toggle **off** when idle: `serena-ni`, `graphify-ni-pipeline`, `unified-search`, `homelab-env-manager`

## Session

New chat after false “done” or > ~80 turns. Handoff: `00_Inbox/handoffs/YYYY-MM-DD-slug.md`.

## Rule retirement (2026-11-11)

| Retired | Replacement |
|---------|-------------|
| Workspace stubs (`ni-pipeline-graph`, `01-database`, `00-mempalace`, `00-ni-stack`) | `_archive/` |
| Global NI duplicates | `_retired/` + skills |
| `projects/.clinerules/workflow.md` (MUST block) | pointer only — disable rule if needed |
