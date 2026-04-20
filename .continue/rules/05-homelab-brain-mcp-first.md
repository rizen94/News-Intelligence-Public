---
name: Homelab brain — MemPalace / Brain Router first
description: Before designing new RAG pipelines or duplicate memory layers, use existing MCP tools (MemPalace, BrainRouter) and mined palace data.
alwaysApply: true
---

# Use the homelab “brain” before new pipelines

This workspace is wired to **HomeLab** memory tooling via Continue MCP (see `.continue/mcpServers/`). Prefer those over ad-hoc duplicate retrieval.

## Order of operations

1. **MemPalace MCP** (`python -m mempalace.mcp_server`) — semantic search, drawers, and palace operations already backed by **mined** project/docs. Use MemPalace tools when the question is “what do we already know / remember about X?” or cross-session recall.

2. **BrainRouter MCP** (`brain_router_mcp_server.py`) — calls **`brain_search`** on the Homelab **Brain Router** HTTP service (`BRAIN_ROUTER_BASE_URL`, default `http://127.0.0.1:18052`). Pass **`sources`** to pull from the right stores in one shot, for example:
   - **`obsidian`** — human-authored vault notes and runbooks (`OBSIDIAN_VAULT_PATH` on the stack).
   - **`mempalace`** — palace-backed snippets (same world as MemPalace MCP when configured).
   - **`khoj`** — searchable knowledge base (Khoj service on the homelab network).
   - **`memory_api`** — optional HTTP memory store when you deliberately want that layer.

   Example intent: “search decisions and runbooks” → include **`obsidian`**; “search indexed docs and articles in Khoj” → include **`khoj`**; “broad recall” → combine **`mempalace`** with others as needed.

3. **Repo tools** (`grep_search`, `glob_search`, `read_file`, `view_repo_map`) — for **source-of-truth code** in this git tree. Memory tools complement the repo; they do not replace reading the actual files for implementation work.

## Do not by default

- Spin up a **second** custom code-RAG or parallel embedding pipeline for “project context” while MemPalace mining + Brain Router + Obsidian/Khoj already cover semantic and human-curated knowledge — unless there is a concrete gap (scale, access, or policy) those tools cannot meet.

## Preconditions

- Brain Router must be **reachable** at `BRAIN_ROUTER_BASE_URL` (compose / host as per HomeLab runbooks).
- MemPalace world must be **initialized and mined** on a schedule you already use; otherwise search results will be thin — fix mining/indexing before adding new stores.

For stack-level detail, read **`HomeLab-AI-Stack/docs/CONTINUE_VSCODE_MCP.md`**, **`docs/MEMPALACE_INTEGRATION.md`**, and **`docs/runbooks/FULL_STACK_OPERATOR_GUIDE.md`** (Brain Router + Obsidian + Khoj).
