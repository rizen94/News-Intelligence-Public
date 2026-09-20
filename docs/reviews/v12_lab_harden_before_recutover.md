# Lab-first hardening (2026-08-16) — continue development before re-cutover

Widow already received an early `/opt` sync to `12.0.0`. Treat that as a **preview deploy**. Further MUST+THIN work lands on PopOS `release/12.0` first; re-rsync to Widow only after this checklist is green.

## Hardening done

| Item | Status |
|------|--------|
| Narrative insufficient_evidence max-rounds → `closed_thin` | Done |
| Route resolvers: max rounds → `closed_thin`; both-zero → editor | Done |
| Shared `storyline_articles_dual_write_enabled()` | Done (default off) |
| Episode attach / founding / admit / narrative_first dual-write gated | Done |
| `services/episode_attach_gate.py` → re-export of shared | Done |
| `POST /packages/from_kernel` + `run_act_verb_kernel.py` | Done |
| Parking-lot triage applied (pkgs 96, 77, 74 → `closed_thin`) | Done (`closed_thin` count = 3) |
| Unit tests v12 suite | Green |

## Still before re-cutover

1. CourtListener token (`COURTLISTENER_API_TOKEN`) then dry-run → live
2. Commit `release/12.0` when ready (ask human)
3. Re-rsync lab → `/opt`; restart API; smoke `docs/reviews/v12_post_cutover_ops.md`

## Hold

LAST bucket (LLM stakes, hops, Edition SPA, ntfy) — unchanged.
