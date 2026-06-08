---
created: 2026-06-06
tags: [decision, news-intelligence, migration, widow, infrastructure]
status: accepted
---

# ADR — News Intelligence Widow migration complete

## Context

News Intelligence ran on the main PopOS/GPU server. June 2026 migration moved the full stack to Widow (`192.168.93.101`) with 70B Ollama offload to the main server (`192.168.93.100`).

## Decision

1. **Migration is complete and final.** All NI development and queries use Widow.
2. **Canonical dev path:** `/home/pete/Documents/projects/News Intelligence` on Widow
3. **Production runtime:** `/opt/news-intelligence` on Widow until dev/prod reconciled
4. **PopOS local NI copy** moves to NAS cold storage (`/mnt/nas/News-Intelligence-Archive-2026-06-03`)
5. **PopOS retains HomeLab only** — no local NI repo after cold storage

## Deprecated

- `/home/pete/projects/News Intelligence` on Widow (stale duplicate)
- Pre-migration three-machine split (Primary API + Widow Postgres only)

## Consequences

- Agents must read `PROJECT_STATUS.md` and `PROJECT_BOUNDARIES.md` before NI work
- Homelab postgres-mcp remains read-only consumer of `news_intel`
- Obsidian and MemPalace updated with post-migration facts

## Related

- [[../20_Projects/news-intelligence]]
- [[../40_Reference/project-boundaries-ni-homelab]]
