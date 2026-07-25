# Storyline assembly / connection logic — review pack

**Purpose:** Smallest footprint for a stronger agent to review whether NI overcomplicates storyline assembly and why membership bags grow while editorial summaries stay thin.

**Do not fix** the operator’s example (`politics` storyline *Trump's Foreign Policy Backfires…* / id **3775**). It is cited only as the symptom pattern.

## Contents

| File | Role |
|------|------|
| [`CONCEPTUAL_REVIEW.md`](CONCEPTUAL_REVIEW.md) | Accepted stronger-model verdict (event co-reference) |
| [`OPERATOR_ANSWERS.md`](OPERATOR_ANSWERS.md) | Locked product decisions + feature flag |
| [`ASSEMBLY_CONNECTION_LOGIC.md`](ASSEMBLY_CONNECTION_LOGIC.md) | Full logic map, failure modes, config knobs |
| [`DB_EXAMPLES.md`](DB_EXAMPLES.md) | Good / bad / mixed examples from live DB (2026-07-24) |
| [`examples.json`](examples.json) | Machine-readable example rows |
| [`repomix-assembly-connection.config.json`](../../../repomix-assembly-connection.config.json) | Minimal source include list |
| `repomix-assembly-connection-output.md` (generated at repo root) | Compressed code pack |

## Generate / refresh the code pack

Direct `repomix -c …` from the workspace root hits a globby permission error on this host. Use a filtered temp tree (same pattern as other NI packs):

```bash
cd "/home/pete/Documents/projects/News Intelligence"
# copy include paths from repomix-assembly-connection.config.json into /tmp/… then:
# npx --yes repomix -c repomix.config.json
# → repomix-assembly-connection-output.md (~61k tokens / ~231 KB compressed, 26 files)
```

Hand the reviewing agent: this folder **plus** repo-root `repomix-assembly-connection-output.md`.

## Review brief (one paragraph)

NI **attaches widely** (entity/ILIKE absorb, politics/finance `aggressive_membership`, HITL only at ~150) then **summarizes narrowly** (keeper filter + LLM evidence caps). High `relevance_score` and `relationship_type=related` do not mean on-theme. Chemistry domains have a 48-member hard cap that is not stopping medicine mega-bags in practice (see examples).
