---
name: ni-serena-symbols
description: >-
  Symbol-level NI code navigation and edits via Serena MCP (LSP). Use when
  refactoring a function/class, finding references, or replacing a symbol body
  — not for pipeline SQL or full-file reads.
---

# NI Serena (symbol tools)

**MCP server:** `serena-ni` (stdio). **Project:** this repo; **5 tools only** (see `.serena/project.yml`).

| Tool | Use |
|------|-----|
| `find_symbol` | Locate definition by name |
| `find_referencing_symbols` | Callers before changing API |
| `get_symbols_overview` | File outline without reading whole file |
| `find_declaration` | Jump to declaration |
| `replace_symbol_body` | Surgical body replace (prefer over whole-file patch) |

## vs Graphify / repomix

| Need | Use |
|------|-----|
| Static call graph / pipeline slice | **ni-graphify** |
| Text / pack grep | **ni-repomix-grep** |
| LSP-accurate symbol ops | **this skill** |

## Ops

- First session may need project activation in Serena UI/dashboard if tools fail.
- Heavy; **disable** `serena-ni` in MCP when not refactoring.
- Wrapper: `scripts/serena_mcp_ni.sh`
