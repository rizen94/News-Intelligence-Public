# Archived: editorial room prompts

**Status:** archived — not on the live desk path.

These prompts belonged to the headless **editorial room loop** (investigation
tags, connection proposals, entity disambiguation). That writer lives behind
`LEGACY_EDITORIAL_WRITERS_ENABLED` / `EDITORIAL_ROOM_LOOP_ENABLED` shims; the
archived Python modules under `api/_archived/editorial/` are the rollback
target (may be absent on some checkouts).

## Live replacements

| Concern | Live path |
|---------|-----------|
| Causal CoT / edge-backed narrative | `api/config/prompts/narrative/causal_narrative.md` + `narrative_reasoning_service.py` |
| Package research / narrative / reduction / compose | `api/config/prompts/{research,narrative,reduction,editor}/` |
| Storyline durable walkthrough | `api/config/prompts/narrative/storyline_walkthrough.md` |

Do **not** put new live prompts here. Restore only if deliberately rolling back
to the archived editorial room loop.
