---
name: ni-operating-principles
description: >-
  Anti-drift habits for News Intelligence — write-once-read-many observability,
  minimal scope, golden trace done criteria, Plan/Act boundaries. Use before
  monitor/metrics/Prometheus/Grafana work, refactors, or any "repair platform"
  task; read after ni-agent.md when user mentions drift, SSOT, or repair plan.
---

# NI operating principles (skill)

**Read:** `docs/OPERATING_PRINCIPLES.md` (full policy).

## Quick binding

1. **Done** = product trace or spine contract moved — not green health alone.
2. **Metrics** = update snapshot/materializer **writers** before Monitor/Prometheus/Grafana **readers**; no new COUNT-on-scrape paths.
3. **Scope** = first broken stage only; grep/repomix before large file reads.
4. **Plan** = handoff with evidence; **Act** = verify + ship (`ni-verify-change`, `ni-ship-widow`).
5. **Silent spine** (pending, no runs) = P0.

## When this skill applies

- Grafana, Prometheus, `ni_*`, backlog snapshot, materializer, Monitor v2
- "Repair", "realign", "technical drift", "SSOT"
- Any ticket where observability changed but reader/spine did not

## Crosswalk

- `docs/monitor_alignment/CROSSWALK.md`
- `docs/NI_REPAIR_PLAN.md` — pick the matching **P0/P1** ID in handoff or commit message
- `docs/AVAILABLE_SERVICES_AND_MCP.md` — which MCP/homelab services to use

## Plan mode

Cite repair plan IDs in **Approved plan** steps. Do not implement OBS/SPINE items in Plan.

## Act mode

After patch: re-run the check that failed (scrape, SQL, golden stage). Reference repair ID in vault append.