# v12 reassessment (2026-08-16) — MUST + THIN complete on PopOS lab

## What shipped (lab `release/12.0`)

| Area | Result |
|------|--------|
| Episode gate | `episode_container_assembly` incorporated+enabled; absorb still off |
| Dual-write | `STORYLINE_ARTICLES_DUAL_WRITE` default false |
| EEL reads | Storyline detail prefers EEL→CE→articles when flag on |
| Publish escape | max-rounds → `closed_thin` (mig 297 applied + ledgered) |
| Auto-republish | `NEWS_STORY_AUTO_REPUBLISH` default false |
| Phase order | evidence expand before reduction; automation + room_loop retired |
| StakesGate | deterministic actor+act+cite + nut graf/walkaway |
| Kernel | `ensure_package_from_kernel` + act-verb top-K |
| Track | reactivation → `watchlist_alerts` |
| Collectors | FR live (50 CE); EDGAR dry-run+live enabled; CourtListener needs token |

## Tests

- `tests/unit/test_v12_must_thin.py` — 8 passed
- Episode gate suite mostly green; one pre-existing missing symbol `evaluate_article_episode_admit`

## Go / no-go for Widow code rsync

**Go for code sync** with env flags already matching Widow (`EPISODE_…=true`, `AUTO_ATTACH=0`).

**Hold NLP / hops / Edition SPA** (LAST bucket) until next reassessment after smoke on `/opt`.

## Open follow-ups (not blocking Widow)

1. Set `COURTLISTENER_API_TOKEN` (Infisical name only) then dry-run → live
2. Frontend still heavy on `storyline_articles` — gradually trust EEL API path
3. Cluster D modules remain live (no blind archive)
4. LAST: LLM stakes, expectation NLP, H1–H6 hops, Edition SPA, spotlight, ntfy

## Recommend next

1. Tag `/opt` v11 archive → rsync lab → restart API → smoke
2. Monitor FR CE volume + closed_thin rate for 24–48h
3. Only then open LAST items
