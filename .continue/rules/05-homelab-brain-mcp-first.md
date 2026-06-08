---
name: Homelab brain — MemPalace / MCP first
description: Before designing new RAG pipelines or duplicate memory layers, use HomeLab MCP tools (MemPalace, Obsidian, Postgres).
alwaysApply: true
---

# Use the homelab “brain” before new pipelines

This workspace connects to **HomeLab MCP** via Continue (`.continue/mcpServers/homelab-mcp-stack.yaml`), synced from **`HomeLab-AI-Stack/config/mcp-stack.json`**.

Re-sync after `.env` port/key changes:

```bash
./scripts/sync-homelab-mcp.sh
```

## Order of operations

1. **MemPalace MCP** (`mempalace` server) — semantic search, drawers, palace operations. Tools are **`mempalace_*` only** (never `query_memories` / `check_memories`).

2. **Obsidian vault MCP** (`obsidian-vault` server) — human-authored vault notes and runbooks on NAS mount.

3. **Postgres MCP** (`postgres-mcp` server) — read-only SQL over **`news_intel`** on Widow (not Homelab local Postgres `:15432`).

4. **Repo tools** — source-of-truth code in this git tree. Memory tools complement the repo; they do not replace reading files for implementation.

## Do not by default

- Spin up a **second** custom code-RAG while MemPalace + Obsidian + Postgres MCP already cover semantic and relational knowledge — unless there is a concrete gap those tools cannot meet.

## Preconditions

- MCP tier running: `docker compose -f HomeLab-AI-Stack/compose/mcp.yaml up -d`
- Gateway healthy: `curl -sf http://127.0.0.1:18443/mempalace/docs`

Stack detail: **`HomeLab-AI-Stack/docs/MCP.md`**, **`HomeLab-AI-Stack/ARCHITECTURE.md`**. Project boundary: **`../PROJECT_BOUNDARIES.md`**.
