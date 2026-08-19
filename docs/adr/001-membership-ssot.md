# ADR 001 — Episode membership SSOT (EEL, not bag)

**Status:** accepted (2026-08-17)  
**Context:** v12 cutover; bag-write leak (~2k rows/day) despite `write_allowed=false`

## Decision

1. **Write SSOT:** `intelligence.event_episode_links` → `chronological_events` → articles. All admits go through [`api/shared/membership_store.py`](../../api/shared/membership_store.py).
2. **Read SSOT:** Same EEL chain via [`api/shared/episode_membership.py`](../../api/shared/episode_membership.py) for list, detail, curation, counts.
3. **`{domain}.storyline_articles`:** Write-frozen in `episode_eel` mode; retained for audit/rollback. Optional dual-write only via `STORYLINE_ARTICLES_DUAL_WRITE=1` (ops migration window).
4. **Failed attach:** Episode metadata (`attach_block_reason`) — no inline bag fallback.

## Mode

See [`membership_mode.py`](../../api/shared/membership_mode.py):

| Mode | When |
|------|------|
| `legacy_bag` | `EPISODE_CONTAINER_ASSEMBLY` off |
| `episode_eel` | Assembly on, dual-write off (v12 default) |
| `episode_eel_dual_write` | Both on (migration only) |

## References

- [ASSEMBLY_MODEL.md](../../api/services/ASSEMBLY_MODEL.md)
- [UPGRADE_12.0.md](../UPGRADE_12.0.md)
- [v12_post_cutover_ops.md](../reviews/v12_post_cutover_ops.md)
