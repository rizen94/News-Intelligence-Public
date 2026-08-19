# Archived editorial writers (v11)

Moved out of the hot path so Editorial Packages / `news_stories` are the v11 product.

## Modules

| Module | Former path | Role |
|--------|-------------|------|
| `editorial_document_service.py` | `api/services/editorial_document_service.py` | Wrote `storylines.editorial_document` as longform product |
| `editorial_room_loop_service.py` | `api/services/editorial_room_loop_service.py` | Desk → vault investigation round |

Live tree keeps thin shims at the old import paths.

## Rollback

```bash
export LEGACY_EDITORIAL_WRITERS_ENABLED=1
export EDITORIAL_ROOM_LOOP_ENABLED=true   # if you need the room loop
```

Local v11 (`.env.dev`) defaults these **off**. Widow may keep room loop on until cutover.

## What is NOT archived

- Storyline tables/columns (`editorial_document`, `canonical_narrative`, `synthesized_markdown`) — read bridges for seed/audit
- `desk_promotion_service` — still flag-gated (`DESK_AGENT_WRITEBACK_ENABLED`, default off)
- `storyline_narrative_finisher_service` — chemistry / refinement, not the reader product
- Migration script `backfill_editorial_packages_from_legacy.py` — **reads** legacy prose into draft `news_stories`
