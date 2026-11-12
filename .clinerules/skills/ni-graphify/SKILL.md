---
name: ni-graphify
description: >-
  Graphify pipeline call graph for NI — refresh slice, MCP graphify-ni-pipeline,
  explain/path vs repomix. Use when you need who-calls-whom, stale graphify MCP,
  or after changing automation/phases/gates/storyline/reader code.
---

# NI Graphify (pipeline slice)

## When to use

**After** `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` §2 when you need **call paths**, not schema rows.

| Need | Tool |
|------|------|
| Call graph | **graphify-ni-pipeline** MCP: `explain`, `path`, `query` |
| Full file text | Repomix + `rg` (not graphify) |
| DB truth | postgres-mcp — skill **ni-postgres** |

## Refresh graph

- **MCP start:** `graphify_mcp_ni.sh` runs `graphify_ni_ensure_graph.sh` if sources are newer than `graph.json`.
- **Manual:** `./scripts/graphify_ni_pipeline_slice.sh`
- **Dev watch:** `./scripts/graphify_ni_watch.sh` (long-running; retry MCP after rebuilds)

Output: `graphify-trial-corpus/pipeline-full/graphify-out/graph.json` (gitignored).

Install: `uv tool install 'graphifyy[mcp]'`. Wiring: `docs/GRAPHIFY_PIPELINE_SLICE.md`.

## Corpus coverage

`automation_manager`, `pipeline_controller`, backlog/admission/gates, RSS collector, storyline discovery/assembly/automation/narrative, `domains_reader`, `domains_storyline_management`.

**Not in graph:** DB rows, Widow runtime, vault/MemPalace.

## Usage

1. Start from a symbol or phase from logs or the runtime doc (e.g. `build_reader_home`, `automation_manager` phase handlers).
2. MCP **explain** → context; **path** → upstream/downstream.
3. Open real files under `api/` — graph paths are **corpus copies** (`services/...`, `domains_reader/...`).

Do not paste `graph.json` into chat or vault.
