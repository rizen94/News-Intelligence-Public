---
name: mempalace-tools
description: >-
  Correct mempalace MCP tool names and server key. Use when searching palace
  memory, drawers, wings, or distilling reusable NI facts — not for pipeline SQL.
---

# MemPalace MCP (tool names)

**Server key:** `mempalace` (not `mempalace-server`, `news-intel-server`).

Use only tools registered in the IDE whose names start with **`mempalace_`**.

## Forbidden (will always fail)

- `query_memories`, `check_memories`, `save_memory`, `get_memory`

Do not invent servers (`news-intel-server`, `get_forecast`, etc.).

## Common tools

| Intent | Tool |
|--------|------|
| Search / recall | `mempalace_search` — args: `query` (required), `limit`; optional `wing` (**News Intelligence**), `room` |
| Structure | `mempalace_list_wings`, `mempalace_get_taxonomy`, `mempalace_list_rooms` |
| Duplicates | `mempalace_check_duplicate` |
| Drawers | `mempalace_get_drawer`, `mempalace_list_drawers`, `mempalace_add_drawer`, `mempalace_update_drawer` |
| After external writers | `mempalace_reconnect` |

## NI context

Wing **News Intelligence**; rooms like `pipeline_handoff` for durable distills — not for live schema (use **ni-postgres**).

## When to skip

Pipeline runtime debug: prefer vault handoff + §2 SQL first; MemPalace is for **reusable** distill, not appeasement after a failed fix.

List tools (optional): `docker exec ai-lab-mcp-gateway /usr/local/bin/python3 -c 'import mempalace.mcp_server as m; print("\n".join(sorted(m.TOOLS)))'`
