# News Intelligence — verify before “done” (required)

Diagnosis without **verified** change is not a fix. Overconfident closure wastes time.

Works with `ni-deep-investigation.md` (evidence) and `ni-implement.md` (when to edit).

---

## Banned claims (unless gates below pass in **this session**)

Do **not** say or imply:

- *fully fixed*, *issue resolved*, *all set*, *deployed to production*, *prod is updated*, *pipeline is working again*
- *I updated the automation* when **no `editor` / patch** ran on the owning module
- *migration applied* without `execute_sql` or command output proving schema/row change **after** apply

Use instead:

- **Proposed** — plan or snippet only
- **Local repo changed** — after `editor`; include path + symbol
- **Verified on Widow** — only after post-check SQL/SSH in this session

---

## Dev fix — definition of done (all required)

| # | Gate | Proof |
|---|------|--------|
| 1 | **Change exists** | `git diff` / `git status` or Cline edit tool on the file you named |
| 2 | **Right layer** | You read the **handler/service/worker** that runs in prod, not a dead script |
| 3 | **Re-check** | Re-run the **same** SQL or test that showed the bug; show **before vs after** (counts, status, timestamps) |
| 4 | **Still broken?** | If re-check fails, say **not fixed** and what failed — no soft landing |

**No file changed in session ⇒ no code fix claim.**

---

## Production / Widow — definition of done

PopOS repo edits **do not** change Widow runtime until an explicit deploy path runs.

| # | Gate | Proof |
|---|------|--------|
| 1 | **Authorization** | User message names **prod / Widow / deploy / apply on 101** (or you asked once and they said yes) |
| 2 | **Deploy command** | **`./scripts/deploy_to_widow.sh`** from repo root (see `ni-deploy.md`) — report exit code; **do not invent** alternate rsync/systemctl |
| 3 | **Revision match** | SSH read-only: prod tree **commit or mtime** matches what you intended to ship |
| 4 | **Service health** | `systemctl is-active` (or user’s unit list) for services you restarted |
| 5 | **Data-plane proof** | Fresh `execute_sql` (e.g. new rows in monitoring tables, updated `last_run`, passing `automation_run_history` phase) |

**Never** claim prod from: local edits only, “should pick up on restart”, or SQL run before deploy.

If deploy docs are missing in context: **stop** and ask for the canonical deploy command — do not guess.

---

## Session close format (mandatory before “success”)

```text
## Status: [Proposed | Local changed | Verified dev | Verified prod]

**Changed:** <paths or "none">
**Deploy:** [not run | command + exit code]
**Re-check SQL/test:** <one line + numbers>
**Still open:** <blockers or "none">
```

If any row is empty or “none” where a fix was claimed, downgrade status to **Proposed** or **Not fixed**.

---

## Common failure mode (this project)

Reporting empty `pipeline.*` monitoring tables as “fixed” after **only** suggesting INSERT statements or config tweaks **without** editing the writer code and seeing new rows on re-query = **wrong**. Fix the **writer path**, then prove rows or history updates.
