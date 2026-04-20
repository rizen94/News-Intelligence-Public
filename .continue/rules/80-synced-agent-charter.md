---

## name: Agent charter (synced from homelab)
description: Cross-stack defaults synced from HomeLab-AI-Stack configs/agent/CHARTER.md — edit there and re-run sync_agent_charter.sh
alwaysApply: true

# Agent charter (canonical)

Edit **this file only** in git, then run `./scripts/sync_agent_charter.sh` (see `configs/agent/README.md`) to push copies into Continue / Cursor rule paths.

## Cross-stack defaults

- Prefer **facts in repo or vault** over memory; use **Brain Router** `brain_search` when policy spans homelab + projects and is not in the open file.
- Do not invent hostnames, ports, API paths, or secrets. Ask or search.
- For **News Intelligence** code and terminology, treat `AGENTS.md` in that repo as authoritative when a clone is present.

## Homelab

- **Brain search:** use `POST /brain/search` with explicit `sources` when you need Obsidian vs MemPalace vs Khoj vs Memory API.
- **MemPalace** is semantic recall; **Obsidian** is human-authored runbooks; keep them aligned when procedures change.

## Security

- LAN-only services; no pasting `.env` contents into chats. Use placeholders in docs.

---

*Add project-specific bullets below; keep short. Long NI detail stays in `News Intelligence/AGENTS.md`.*