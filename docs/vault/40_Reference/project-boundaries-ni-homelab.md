---
created: 2026-06-06
tags: [reference, boundaries, news-intelligence, homelab, postgres]
---

# Project boundaries — News Intelligence vs HomeLab

Mirror of `~/Documents/projects/PROJECT_BOUNDARIES.md`.

## Quick rule

> When **postgres-mcp** returns SQL rows, you are reading **News Intelligence** data on Widow — not the Homelab app layer.

## Postgres ports

| Port | What |
|------|------|
| **5432** Widow | NI `news_intel` (NI owns) |
| **18090** PopOS | Homelab Postgres MCP (read-only bridge) |
| **15432** PopOS | Homelab local Postgres (Open WebUI only) |

## Ownership

| | News Intelligence | HomeLab |
|--|-------------------|---------|
| Host | Widow `.101` | PopOS `.99` |
| Repo | Widow `Documents/projects/News Intelligence` | `HomeLab-AI-Stack/` |
| Postgres | Owns `news_intel` | Reads via MCP; local `:15432` separate |

## Env cross-reference (names only)

- Homelab: `NEWS_INTEL_DATABASE_URI`
- NI (Widow): `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

Full index: [[secrets-and-settings-index]]
