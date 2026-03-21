# Source credibility tiers (orchestrator governance)

**Config:** `api/config/orchestrator_governance.yaml` → section **`source_credibility`**.

**Loader / resolver:** `api/shared/services/source_credibility_service.py`

## Behaviour

| Step | What happens |
|------|----------------|
| **RSS ingest** | After heuristic `quality_score`, optionally multiply by tier **`multiplier`** (`apply_to_quality_score`). Store tier payload under **`articles.metadata.source_credibility`**. |
| **Context** | `ensure_context_for_article` copies **`source_credibility`** from the article into **`intelligence.contexts.metadata`**. |
| **Claim extraction** | Stored claim **`confidence`** is multiplied by the context’s **`source_credibility.multiplier`** (capped to `[0, 1]`). |

## Tuning

- **`enabled: false`** — no scaling, multiplier treated as 1.0 for quality; metadata still omits tier unless you re-enable.
- **`apply_to_quality_score: false`** — keep tier metadata for downstream use only; do not change RSS `quality_score`.
- **`tier_order`** — first tier whose `host_suffixes`, `host_contains`, or `name_keywords` matches wins.
- **`default_tier`** — used when no tier patterns match (typically long-tail RSS with multiplier &lt; 1).

## Future hooks

- **`requires_corroboration`** — stored in metadata for UI / analytics; not yet enforced by automation (e.g. second-source check before promotion).

## Related

- [ORCHESTRATOR_DEVELOPMENT_PLAN.md](ORCHESTRATOR_DEVELOPMENT_PLAN.md) (orchestrator context)
- [CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md](CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md) (claim confidence + promotion)
