---
name: ni-pipeline-debug
description: >-
  News Intelligence pipeline and runtime investigation ladder. Use when debugging
  automation, heartbeats, phases, Widow prod symptoms, stale pipeline SQL,
  or before any NI code fix. Invoke at task start for pipeline work.
---

# NI pipeline / runtime debug

Execute this ladder **in order**. Do not skip to code, INSERT seed data, or a narrative "Final Answer".

**Product symptoms** (empty home feed, briefs, RSS → UI): activate **`ni-golden-trace`** first — pick `golden_article_id`, find **first broken stage**, then use this ladder only for stages 1–4 evidence (bounded).

## Resume

If continuing a job: `vault_read_note` on `00_Inbox/handoffs/YYYY-MM-DD-<slug>.md` (goal at top). Do not re-discover from scratch.

## Steps

1. **`docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` §2** — evidence ladder (services, health, SQL). Do not invent schema or tables.
2. **`./scripts/repomix_pack_ni.sh`** — refresh `api/repomix-output.xml` if missing or code changed since last pack.
3. **`rg` / `grep_repomix_output`** — phase name, error string, or symbol from §2/§3 of the runtime doc.
4. **`postgres-mcp`** — bounded SQL **from the doc** (e.g. §2D heartbeats, §2F run history). `LIMIT` ≤ 50. Use skill **ni-postgres** if unsure which DB or tool order.
5. **Call paths only when needed** — skill **ni-graphify** (refresh graph if stale) after step 1–2.
6. **Implement** — Plan: `plan_code_change` only. Act: `editor` / `run_commands` when authorized.
7. **Ship** — user authorized Widow → activate skill **ni-ship-widow**.

## Notes (efficiency)

- After each **proved** fact: one short `vault_append_note` to the handoff; keep chat to bullets.
- *Proposed* = narrative only. *Done* = diff or deploy exit code + §2 re-check.
- Empty table ≠ fix with INSERT. Grep who **reads/writes** the table vs what the endpoint uses.

## Anti-patterns (failure)

- Long analysis, no vault write, repeating the same reads.
- MemPalace/vault theater **after** cosmetic SQL with **no** `api/` patch.
- Monitoring/scheduling patch with **no** golden `article_id` stage movement on reader tickets.
