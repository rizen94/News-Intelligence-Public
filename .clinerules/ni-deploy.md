# News Intelligence — deploy (Widow)

When the user says **deploy**, **ship**, **push to Widow**, **production**, or **run deploy** — you **must execute** the workflow below with **run_commands**, not a markdown-only checklist.

**Do not** claim you cannot access production or execute scripts. Cline on PopOS has SSH to Widow with auto-approve when enabled.

## Canonical path (PopOS → Widow)

| Step | Command |
|------|---------|
| 1. Repo root | `~/Documents/projects/news_intelligence` (this workspace) |
| 2. Commit (if user asked to ship code) | `git add … && git commit -m "…"` |
| 3. Deploy | `./scripts/deploy_to_widow.sh` from repo root |
| 4. Verify | Script ends with post-deploy smoke tests; plus `postgres-mcp` re-check SQL for the bug |

**Script does:** rsync → `/opt/news-intelligence` on **`pete@192.168.93.101`**, `setup_widow_app.sh`, migrations, **`news-intelligence-api-public`** restart, curl smoke tests.

**Secrets:** `.env` on Widow only — never paste `DB_PASSWORD` in chat.

## Optional

| Task | Script |
|------|--------|
| Public SPA bundle | `./scripts/deploy_public_demo_to_widow.sh` |
| API restart only | `./scripts/restart_api_with_db.sh` (see `scripts/ni_review/scripts/SCRIPTS_INDEX.md`) |

## After deploy (`ni-verify-completion.md`)

- SSH read-only: `systemctl is-active news-intelligence-api-public`; `cat /opt/news-intelligence/BUILD_INFO`
- Same **`execute_sql`** that showed the bug — show **after** counts/status

## Overrides `workflow.md` “blocked”

Explicit user **deploy** authorization overrides the generic “production deployment blocked” line in `workflow.md` for **this** run — run the script and report exit code + tail output.
