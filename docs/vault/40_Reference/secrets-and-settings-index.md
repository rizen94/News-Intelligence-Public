---
created: 2026-06-06
tags: [reference, secrets, settings, env]
---

# Secrets and settings index (paths only)

**No live passwords in this note.**

## Authoritative `.env` files

| Project | Host | Path |
|---------|------|------|
| HomeLab | PopOS | `~/Documents/projects/HomeLab-AI-Stack/.env` |
| News Intelligence | Widow | `News Intelligence/configs/.env` |

## Password files

| File | Location |
|------|----------|
| `.db_password_widow` | Widow NI project root |

## Cross-project DB

| Var (Homelab) | Target |
|---------------|--------|
| `NEWS_INTEL_DATABASE_URI` | Widow `192.168.93.101:5432/news_intel` |

Homelab `POSTGRES_*` on `:15432` is **not** NI.

## MCP sync

- `HomeLab-AI-Stack/config/mcp-stack.json`
- `HomeLab-AI-Stack/scripts/sync-agent-mcp.sh`

## Vault / palace

- Obsidian: `/mnt/obsidian-vault`
- MemPalace: `ai-lab/brain/palace`

Canonical doc: `HomeLab-AI-Stack/docs/SECRETS_AND_SETTINGS_INDEX.md`
