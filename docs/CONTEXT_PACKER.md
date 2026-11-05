# Context Packer — Usage Guide

## What it does

`scripts/context_pack.py` compresses a project's documentation, codebase structure, and active state into one `ONBOARDING_CONTEXT.md` file. It replaces the need to manually piece together AGENTS.md, CODEBASE_MAP, PROJECT_STATUS, DATABASE.md, and architecture docs when handing off work to yourself or an AI agent.

**Problem solved:** "I don't know where to start" / "What's changed since last time?" are the two biggest sources of context-loss in large multi-repo initiatives.

## Quick start

```bash
# News Intelligence (default)
cd ~/Documents/projects/News\ Intelligence
python scripts/context_pack.py

# HomeLab-AI-Stack
python scripts/context_pack.py --project HomeLab-AI-Stack

# Custom output path
python scripts/context_pack.py -o ~/tmp/handoff.md

# Preview only (don't write)
python scripts/context_pack.py --dry-run
```

Output: `docs/ONBOARDING_CONTEXT.md` (~10 pages for NI, ~1 page for HomeLab)

## What's included (live data, not static)

| Section | Source | Refreshes on run? |
|---------|--------|-------------------|
| Purpose & Identity | README.md + AGENTS.md | Yes |
| Host Guardrails | AGENTS.md | Yes |
| Terminology | AGENTS.md table | Yes (if docs change) |
| Entry Points | AGENTS.md table | Yes |
| Architecture & Flow | SYSTEM_OVERVIEW.md, PIPELINE docs | Yes |
| Database config | DATABASE.md | Yes |
| Live File Layout | `Path.iterdir()` scan | **Yes** (live tree) |
| Current Status / Open Items | PROJECT_STATUS.md | Yes |
| Key Decisions / ADRs | KEY_DECISIONS.md (if exists) | Yes |
| MemPalace Audit | MEMPALACE_NI.md | Yes |
| Environment & Config | SETUP_ENV_AND_RUNTIME.md | Yes |
| Recent Git Activity | `git log --since=30d` filtered | **Yes** (real-time) |

## Sections that need manual entry (not auto-discovered yet)

- Terminology table — currently copied from AGENTS.md, not scanned from code constants
- Active services / running processes — would need `systemctl list-units` or HEM API
- Open Pull Requests / PRs — no integration with GitHub/Bitbucket APIs
- Team members / on-call — would need external directory

These are marked **Future Development** (see below).

## How to use the output

1. **New contributor reads:** Purpose -> Entry Points -> Architecture -> File Tree
2. **You're picking up work:** Open Context Pack + PROJECT_STATUS.md (open items)
3. **Handing off to an agent:** Attach ONBOARDING_CONTEXT.md as context before any task
4. **Agent reads it back:** Uses it for terminology, entry points, file locations

## Regeneration policy

Regenerate the pack:
- After major architectural changes
- Before any handoff / PR review that involves unfamiliar code
- Weekly (consider adding to your Monday routine)
- After completing a milestone or merging significant refactors

Do NOT regenerate before every commit — it's a weekly-or-event-based document.

## Future Development (from gap analysis)

| # | Feature | Status | Priority |
|---|---------|--------|----------|
| 1 | **Context Packer** (this tool) | Done | Built |
| 2 | Change-Impact Analysis Hook | **Future Dev** — Pre-commit script detecting doc/code drift | Medium |
| 3 | ADR Integration | **Future Dev** — Formalize architecture decisions with auto-triggered references | Medium-High |
| 4 | Automated Dependency Graphs | **Future Dev** — Live Mermaid graphs from import scanning | Medium |
| 5 | Doc Freshness Score | **Future Development** — Script docs against source mtime for staleness detection | Low |

## Implementation notes

- Pure Python, no external dependencies (uses `pathlib`, `subprocess`)
- Works on both News Intelligence and HomeLab-AI-Stack from a single script
- Tree scan limited to depth=2, breadth=6 per node to keep output manageable
- Git log filtered for doc/config commits; full log appended at bottom for reference
- Output is markdown-friendly for pasting into agent context windows

## File size benchmarks

| Project | Chars | Pages (at 60 lines/page) |
|---------|-------|--------------------------|
| News Intelligence | ~11,400 | ~4 pages |
| HomeLab-AI-Stack | ~2,200 | ~1 page |

