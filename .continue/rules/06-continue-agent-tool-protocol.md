---
name: Continue Agent — MCP tools (no fake XML)
description: How MemPalace and Brain Router tools are invoked in Continue Agent mode; prevents bogus tool-call syntax.
alwaysApply: true
---

# Continue Agent + MCP — not manual XML

## Do not type pseudo tool calls

Strings like `<function=mempalace_search>`, `<parameter=query>...</parameter>`, or `</tool_call>` are **not** valid Continue, OpenAI-style JSON tools, or MCP wire format. If the **model** prints them, Continue cannot execute them — you see a **broken / invalid tool** message and nothing runs.

**You:** describe the task in **plain language** in **Agent mode** (tools enabled). Continue sends **JSON** tool requests to MCP; you do not author tool XML yourself.

## Correct tool names (when MCP is connected)

From this workspace’s MCP servers:

- **MemPalace:** `mempalace_search` (parameters like **`query`**, optional **`limit`**, **`wing`**, **`room`** — see server docs / tool schema in the IDE).
- **Brain Router:** `brain_search` with **`query`**, optional **`limit`**, **`scope`**, **`sources`** (e.g. `["mempalace","obsidian","khoj","memory_api"]`).

If a tool name is wrong or the server is down, the call fails — fix **names** and **runtime** (Brain Router HTTP at `BRAIN_ROUTER_BASE_URL`), not the delimiter tags.

## Model choice

**Agent mode** needs a **chat** model with reliable **tool calling**. If one model keeps emitting garbage tool syntax, switch the active **Chat / Agent** model in Continue to the other Ollama model in `.continue/config.yaml` (both declare **`capabilities: [tool_use]`**).

## Preconditions

- **Agent mode**, not plain Chat (Chat has **no** MCP tools per Continue docs).
- MCP servers show as connected; **Brain Router** container/process reachable if you expect `brain_search`.
