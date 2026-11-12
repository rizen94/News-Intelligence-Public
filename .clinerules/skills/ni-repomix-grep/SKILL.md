---
name: ni-repomix-grep
description: >-
  Search News Intelligence API code before editing — repomix pack, ripgrep on
  repomix-output.xml, grep_repomix_output MCP, find callers and definitions.
  Use for API refactors, new features, "where is X", or any code change that
  is not a full pipeline runtime debug.
---

# NI repomix + grep (search before edit)

**Not pipeline runtime?** Use this skill instead of loading the full `ni-pipeline-debug` ladder. For Widow symptoms start with **`ni-pipeline-debug`**.

## Pack (api/ only)

```bash
./scripts/repomix_pack_ni.sh
```

- **Output:** repo-root `repomix-output.xml` (from `api/` via `repomix.config.json`).
- **When to refresh:** before grep if pack missing; after large `api/` changes; after deploy if symbols look stale.
- Do not full-repo repomix (stray root dir breaks scan — script packs `api/` only).

## Search

**Local (preferred):**

```bash
rg -n "SYMBOL_OR_STRING" repomix-output.xml
rg -n "SYMBOL" api/ --glob '*.py'   # when you know path area
```

**MCP (if `grep_repomix_output` / repomix server is connected):**

- Query against packed output after pack is fresh — same discipline as local `rg`.

## Before changing a symbol

1. Grep **definitions** and **callers** / imports.
2. One sentence what + why before edits (`docs/CODING_STYLE_GUIDE.md` checklist).
3. Fix the bug before adjacent features.

## Pipeline symbols

For automation/phases/heartbeats, also see `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` §1 symbol map — or skill **`ni-pipeline-debug`**.

## After edits

Skill **`ni-verify-change`**.
