# MemPalace MCP — mandatory tool names

**Workspace:** If Cline’s **Open Folder** root is **`Documents/projects`** (monorepo), Cline loads **`projects/.clinerules/`** — not this file alone. Same content is mirrored at **`projects/.clinerules/00-mempalace-mcp.md`** and **`projects/.cursorrules`**.

When using the **`mempalace`** MCP server, only call tools whose names start with **`mempalace_`**.

**Forbidden (not registered — they will always fail):**

- `query_memories`, `check_memories`, `save_memory`, `get_memory`

**Do not invent MCP servers** (e.g. `news-intel-server`, `get_forecast`). Use the **connected** server list in this IDE. News Intelligence data is in this **repository** and **Postgres** (`postgres-mcp` when configured); weather APIs are unrelated.

**Correct calls:**

| Intent | Tool |
|--------|------|
| Search / recall | `mempalace_search` — args include `query`, `limit`; optional `wing`: **`News Intelligence`** |
| Wings / taxonomy | `mempalace_list_wings`, `mempalace_get_taxonomy`, `mempalace_list_rooms` |
| Duplicate check | `mempalace_check_duplicate` |
| Drawers | `mempalace_get_drawer`, `mempalace_add_drawer`, `mempalace_update_drawer`, `mempalace_list_drawers` |
| After mine / external writes | `mempalace_reconnect` |

Operator context for this project is in **AGENTS.md** (MemPalace wing **News Intelligence**, rooms like `pipeline_handoff`).

List registered tools (optional): `docker exec ai-lab-mcp-gateway /usr/local/bin/python3 -c 'import mempalace.mcp_server as m; print("\n".join(sorted(m.TOOLS)))'`
