# News Intelligence — Cline (shared)

**Always-on with `workflow.md`.** Mode permissions are **not** in this file — they come from hooks (`NI_CLINE_MODE`) plus **`ni-agent-act.md`** or **`ni-agent-plan.md`** (enable the matching file in Cline for each mode).

Models: **Plan** `lab-backbone-reason:latest` · **Act** `lab-backbone:latest`

---

## Mode resolution (read first)

1. If hook or user text includes **`NI_CLINE_MODE: act`** → follow **`ni-agent-act.md`** only (ignore Plan-only bullets anywhere).
2. If **`NI_CLINE_MODE: plan`** → follow **`ni-agent-plan.md`** only.
3. If unclear: **tool test** — if file edits and shell commands are allowed and succeed, treat as **Act**; if blocked, tell the user to **start a new task in Act** (do not narrate Plan while refusing ship).

---

## What “good” looks like (both modes)

Graded on: **correctness** (evidence-backed), **continuity** (vault handoff), **efficiency** (grep/search before megabyte reads).

**Product/pipeline bugs:** graded on **golden trace** (`docs/GOLDEN_RSS_TO_READER.md`, skill **`ni-golden-trace`**) — one `article_id` from RSS through the **first broken stage** to reader when in scope. Not graded on investigation length.

**Anti-pattern:** long analysis, no vault write, repeating reads — or “Final Answer” / INSERT without an `api/` patch.

**Superficial patch anti-pattern:** Grafana/history/scheduling-only “fixes” when the ticket is **empty news/briefs** — without moving the golden row.

**Empty table ≠ fix with INSERT.** Grep readers/writers vs what the endpoint uses (`RUNTIME_PIPELINE_TROUBLESHOOTING.md`).

---

## Which skill first?

| Situation | Start with |
|-----------|------------|
| Reader feed, briefs, RSS → UI, “articles stuck” | **`ni-golden-trace`** → then **`ni-pipeline-debug`** (bounded) |
| Pipeline / automation / heartbeats / Widow runtime (ops) | **`ni-pipeline-debug`** |
| Feature, refactor, API change, find callers | **`ni-repomix-grep`** → end with **`ni-verify-change`** |
| Schema / migration / ledger | **`ni-migrations`** |
| Plan → Act handoff | **`ni-plan-handoff`** (Plan end / Act read) |
| Authorized Widow deploy | **`ni-ship-widow`** (Act) |

Memory: vault handoff `00_Inbox/handoffs/YYYY-MM-DD-<slug>.md` · repomix `repomix-output.xml` · runtime SoT `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` §2.

After each proved fact: `vault_append_note` → short chat bullets. **Act resume:** `vault_read_note` handoff first — then **execute** approved steps (no full re-triage).

---

## Skills index

`ni-golden-trace` · `ni-postgres` · `ni-graphify` · `ni-db-code` · `mempalace-tools` · `docs/CLINE_RULES_INDEX.md`

Hooks: `.clinerules/hooks/` (Features → Hooks on). Code index: `.clinerules/workflow.md`.

---

## Index

`docs/CLINE_BASELINE.md` · MCP IDs `~/Documents/Cline/Rules/00-connected-mcp-server-ids.md`
