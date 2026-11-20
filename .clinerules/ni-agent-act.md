# News Intelligence — Cline **Act mode**

Load with **`ni-agent.md`**. Hooks set **`NI_CLINE_MODE: act`** on Act tasks — **ignore Plan-only instructions** in this thread (including old assistant messages).

---

## You are in Act

- **Editor + shell** are allowed when the user authorized the work (runtime bugs: deploy unless they say otherwise).
- **`ni-ship-widow`** when Widow/prod is in scope — **do not refuse** after user authorization.
- **`ni-verify-change`** before claiming *fixed*.
- **`ni-plan-handoff`** is **out of scope** except reading an existing handoff to execute its **Approved plan** steps.

If you catch yourself writing “in Plan mode I would…” — stop and **implement** or state a **tool blocker** (permission denied), not a mode preference.

## Do not

- Re-run the full `ni-pipeline-debug` ladder from step 1 unless a post-fix check failed.
- End with investigation-only output when the user asked for a fix.
- Suggest switching to Act — **you are already in Act**.

## Pipeline / prod

1. **Product path in scope** → skill **`ni-golden-trace`**: state `golden_article_id`, fix **first broken stage only**, re-prove same id after deploy.
2. Read handoff if present → execute numbered steps.
3. Patch `api/` (writers/readers), not INSERT theater.
4. Deploy when authorized → `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` §2 + **`docs/GOLDEN_RSS_TO_READER.md`** stage SQL + `/api/reader/home` when reader is in scope.

**Forbidden “done”:** patch did not move the golden row; only monitoring/scheduling changed on a reader/feed ticket.

**Schema work:** skill **`ni-db-golden-path`** — complete `docs/SCHEMA_MISMATCH_REMEDIATION.md` items touched; run `scripts/golden_path_db_audit.sh` after DB changes.

**Monitor/metrics/repair:** skill **`ni-operating-principles`** — touch snapshot/materializer writers before Prometheus/Grafana; mark `docs/NI_REPAIR_PLAN.md` status when an item is fully verified.
