# Workflow — code & migrations (index)

**Behavior:** `ni-agent.md`

| Kind of work | Skill |
|--------------|--------|
| Pipeline / Widow runtime | `ni-pipeline-debug` |
| Search before edit / refactors | `ni-repomix-grep` |
| SQL migrations / ledger | `ni-migrations` |
| After edits / “is it done?” | `ni-verify-change` |
| Deploy Widow | `ni-ship-widow` |

## Always

- One sentence what + why before edits.
- Commits: `type(scope): description`.
- **Operating principles:** `docs/OPERATING_PRINCIPLES.md` — smallest correct diff; no new COUNT paths for metrics; golden trace or spine contract for “done”.
- **MCP/services:** `docs/AVAILABLE_SERVICES_AND_MCP.md` — use `postgres-mcp` for evidence SQL; do not invent server IDs.

## Blocked without explicit approval

- Delete outside `archive/`
- Edit `api/shared/database/connection.py`
- Undocumented prod steps — use `deploy_to_widow.sh` when user authorizes (skill `ni-ship-widow`)

Style reference: `docs/CODING_STYLE_GUIDE.md`
