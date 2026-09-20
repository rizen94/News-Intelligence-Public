# Editorial package quality (v12)

Operational guide for theme attach gates, published odd-man-out prune, stamp backfill,
and auto-republish. Code lives under `api/shared/editorial_package_attach_gate.py`,
`api/services/published_odd_man_out_service.py`, and `api/services/news_story_service.py`.

## Theme / geo attach gate

Before `add_member`, storyline seed, continuation refresh, and research/narrative LLM
attach candidates are scored for `theme_mismatch`, `unrelated`, `geo_mismatch`, and
`entity_mismatch`. Blocked candidates are **skipped** (not `suppress_reattach`).

When `working_title` is thin (auto stub like `From politics storyline 7697`), the gate
falls back to the **storyline episode title** for spine matching.

## Published odd-man-out prune

Shared service: `api/services/published_odd_man_out_service.py`

- Deterministic reduction flags (optional `--llm`)
- Sticky uncouple + citation scrub on published stories
- Stamps `metadata.last_odd_man_out_at` and `last_odd_man_out_active_count`
- Does **not** change package status (stays `published`)

### Batch CLI

```bash
cd /opt/news-intelligence && set -a && source .env && set +a
PYTHONPATH=api .venv/bin/python api/scripts/prune_published_odd_members.py --limit 20
PYTHONPATH=api .venv/bin/python api/scripts/prune_published_odd_members.py --all --apply
PYTHONPATH=api .venv/bin/python api/scripts/prune_published_odd_members.py --all --apply --republish --extractive
```

## Stamp backfill (post batch prune)

After an offline batch prune that did not stamp metadata, run once:

```bash
PYTHONPATH=api .venv/bin/python api/scripts/backfill_odd_man_out_stamps.py --dry-run
PYTHONPATH=api .venv/bin/python api/scripts/backfill_odd_man_out_stamps.py --apply
```

Sets `last_odd_man_out_at` + active member count and refreshes `readiness` so
`membership_drift_since_prune` works going forward.

## Fleet re-prune (post backfill)

Stamps alone do not remove legacy off-theme members already on disk. Re-prune the
published fleet deterministically, then optionally extractive-republish:

```bash
PYTHONPATH=api .venv/bin/python api/scripts/reprise_published_fleet.py --dry-run --all
PYTHONPATH=api .venv/bin/python api/scripts/reprise_published_fleet.py --apply --all
PYTHONPATH=api .venv/bin/python api/scripts/reprise_published_fleet.py --apply --all --republish --extractive
```

## Online prune before auto-republish

`auto_republish_for_new_members` (`NEWS_STORY_AUTO_REPUBLISH=true`) runs
`prune_package_sync` before compose when new citeable members arrive on a published
package (e.g. story continuation refresh).

Publish path uses **extractive compose fallback** when the LLM assemble fails (Ollama
503 / insufficient): sets `EDITORIAL_COMPOSE_SKIP_LLM=1` and retries once.

## Readiness drift

`compute_readiness` sets `reduction_cleared=false` and `membership_drift_since_prune=true`
for `published` packages when:

- `last_odd_man_out_at` is missing, or
- active member count grew past `last_odd_man_out_active_count`, or
- any active member has `added_at` after the stamp

## Member refresh metrics

`add_member` no longer bumps `added_at` on UPSERT when the row was already `active`
(idempotent storyline refresh). `member_added` decisions are not logged for those refreshes.

## Chronological event domain membership

`chronological_events.tags` are historically ~empty. `search_attachable` therefore
resolves domain via **`source_article_id` ∈ `{domain}.articles`** (not empty-tag
fallthrough to `domain_list[0]`). New extractions stamp `tags=[domain_key]` at
save time (`event_extraction_service.save_events`).

## Research Assemble attach discipline

`assemble_from_idea` (`api/services/research_assemble_service.py`):

1. Runs **interpret search queries** first, then **interpret entity names**.
2. `attach_search_hits` applies the **theme/geo gate** (skips off-theme hits).
3. Headline bait tokens (`Revealed`, `How`, …) are never used as search entities.
4. If an interpret brief’s queries + entities yield **zero** on-theme attaches →
   `closed_thin` (`assemble_no_on_theme_hits`) instead of backfilling from leftover
   capital tokens or the raw idea string.

See also: Research Assemble SPA → `/{domain}/research/assemble`.
