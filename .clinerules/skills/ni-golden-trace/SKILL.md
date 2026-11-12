---
name: ni-golden-trace
description: >-
  Root-cause closure for NI product pipeline work. Use when fixing reader feed,
  briefs, RSS-to-storyline flow, or "articles not showing". Requires one
  golden article_id traced intake→reader—not superficial monitoring patches.
---

# NI golden trace (root cause — product path)

**Doc:** `docs/GOLDEN_RSS_TO_READER.md`

## Bind at task start

When the user cares about **readable material** (news, briefs, home feed, RSS → UI):

1. Select **`golden_article_id`** (latest RSS row or user-specified). State it in chat.
2. Run stage SQL from the doc for that id **before** proposing code.
3. Identify **first broken stage** (1–5). All work in this session targets **only that stage** unless disproven.

## Definition of done (overrides generic “verify”)

| Allowed “done” | Not done |
|----------------|----------|
| Golden row advances **at least one stage** after patch + Widow deploy | Grafana/history-only change on a product ticket |
| `ni-verify-change` + stage SQL + reader curl when stage ≥ 5 | `COUNT(articles)` without golden row |
| Blocker: stage N + **log/journal line** + next action | Vault narrative, no command output |
| Ops-only ticket explicitly scoped by user | Scheduling tweak with no row movement |

## Skill order

1. **`ni-pipeline-debug`** steps 1–4 (bounded) — stop when first broken stage is known.
2. **`ni-repomix-grep`** — writer/executor for **that stage only**.
3. Act: patch → **`ni-ship-widow`** if runtime → re-run **same** golden SQL → reader curl if applicable.

Plan mode: golden id + stage diagnosis + approved steps in **`ni-plan-handoff`** — no “recommendations only” without naming stage N.

## Anti-patterns (reject self)

- Patch `automation_run_history` / Grafana when ticket is empty **news**.
- Fix reader SQL before enrichment/storyline produces dek inputs.
- Stack multiple unrelated patches if the first did not move the golden row.
- Claim “pipeline busy” without phase completion proof for the stage you changed.
