# Project Context Protocol

Superseded for daily work by **`ni-retrieval-ladder.md`** and **`ni-session-vault.md`**.

## Architecture
- Routes: `api/domains/{domain}/routes/`
- Services: `api/services/`
- DB: `api/database/`

## Search before edit
1. `grep_repomix_output` or ripgrep (`repomix-output.xml` from `./scripts/repomix_pack_ni.sh`)
2. Open **only** the files grep names

Do **not** `pack_codebase` in MCP mid-chat. Refresh pack on disk once per job if stale.
