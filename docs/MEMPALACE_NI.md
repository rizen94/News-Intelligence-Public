# MemPalace for News Intelligence

Operator / process memory for NI lives in Homelab MemPalace. Application RAG and Wikipedia are separate — see [`RAG_AND_WIKIPEDIA.md`](RAG_AND_WIKIPEDIA.md). Product intent that belongs in drawers: [`KNOWLEDGE_LOOP.md`](KNOWLEDGE_LOOP.md).

## Canonical wing and rooms

| Use | Wing | Rooms |
|-----|------|-------|
| **Runtime editorial** (Morning Briefing Manager) | `News Intelligence` | `watches`, `preferred_narratives`, `skip_list`, `brief_diary`, `morning_brief` |
| **Agent / process decisions** | Prefer `News Intelligence` → `decisions` (also large mined corpus under `news_intelligence`) | `decisions`, `ops`, `pipeline`, `diary`, … |

Code constants: `MEMPALACE_BRIEF_WING` / `MEMPALACE_ROOMS` in [`api/shared/vault_note_contract.py`](../api/shared/vault_note_contract.py). HTTP client: [`api/services/mempalace_brief_memory.py`](../api/services/mempalace_brief_memory.py) (`MEMPALACE_HTTP_BASE`, fail-soft).

MCP tools: **`mempalace_*` only** (see `.cursor/rules/mempalace-mcp-tools.mdc`).

## Audit snapshot (2026-10-08)

- Palace healthy; brief rooms populated; Widow authority present in KG + drawers.
- **Wing split:** `News Intelligence` (~90 curated/runtime) vs `news_intelligence` (~5k mined docs). Prefer filing new decisions under `News Intelligence`.
- **Search:** Unfiltered / `news_intelligence` searches work. Wing filter `wing=News Intelligence` returns `Error finding id` (block cold-storage checklist item until fixed or wings consolidated).
- **Missing vs code:** `morning_brief` room not listed under `News Intelligence` (code still names it).

Cold-storage checklist status: [`../PROJECT_STATUS.md`](../PROJECT_STATUS.md) (item 2 kept open with evidence).

## Hygiene expectations

1. Before claiming a fact about NI host/path/intent: `mempalace_search` (try without wing if filter fails) + `mempalace_kg_query` for `News Intelligence`.
2. After durable product decisions: `mempalace_check_duplicate` then `mempalace_add_drawer` to wing `News Intelligence`, room `decisions`.
3. Do not invent a second memory store for process notes while MemPalace is available.
4. Runtime briefs must keep working if MemPalace is down (already fail-soft in code).
