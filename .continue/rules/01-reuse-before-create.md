---
name: Reuse before create
description: Search active + archived code before adding files; never duplicate parallel implementations
alwaysApply: true
---

# Reuse before create

Before adding a **new** file, service, component, or route:

1. **Search the active tree** for similar names, behaviour, or routes.
2. **Search archives** when the active tree is thin:
   - `archive/` (if present)
   - `web/_archived_duplicates/`
   - `api/_archived/`
   - `scripts/archive/`
   - `docs/archive/`
3. **Read matches** and decide: **extend**, **restore + modernize**, or **consolidate** — create new only as a last resort.

## Hard bans

- Do **not** add names like **`Enhanced*`, `New*`, `Improved*`, `V2*`** — improve the original module.
- Do **not** add a **parallel** implementation when an extension point already exists.
- Do **not** duplicate logic — extract shared helpers instead.
- Restoring archived **frontend** `.js` → convert to **`.tsx` / `.ts`** when bringing it back.

## When proposing work

If archived code solves the problem, **say so** and prefer restore over rewriting from scratch.
