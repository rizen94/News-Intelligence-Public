# Signal-first steady state — operator levers

Reduce processing load by running **full LLM phases** only on high-signal articles while keeping RSS intake and enrichment broad.

## Measure first

```bash
PYTHONPATH=api uv run python api/scripts/intake_processing_ratio.py
PYTHONPATH=api uv run python api/scripts/rss_feed_yield_report.py
```

Monitor also exposes `signal_lane_metrics`, `feed_health_metrics`, and `intake_first_pass_sum` on `/api/system_monitoring/processing_progress`.

## Enable signal-first (after reviewing ratio report)

| Env | Default | Effect |
|-----|---------|--------|
| `ARTICLE_SIGNAL_ENABLED` | `false` | Master switch for full/light lanes |
| `ARTICLE_SIGNAL_FULL_MIN_QUALITY` | `0.45` | Min `quality_score` for full lane (tier_2+) |
| `ARTICLE_SIGNAL_TRENDING_TOP_N` | `15` | Top clusters (72h) promote articles to full lane |
| `UNIFIED_INTAKE_EXTRACTION_ENABLED` | — | Keep `true` to avoid duplicate legacy extract phases |

YAML mirror: `orchestrator_governance.yaml` → `signal_first` and `quality_thresholds.min_importance_for_processing` (0.45).

**Target:** `signal_processing_ratio` ≈ **15–35%** (`full_llm / articles_created_24h`).

## Backlog burn-down levers (no code deploy)

| Env | Effect |
|-----|--------|
| `PIPELINE_BACKFILL_MODE=true` | Pause new article selection during catch-up |
| `PIPELINE_BACKFILL_COLLECTION_RESUME_AT` | When to resume RSS |
| `COLLECTION_THROTTLE_PENDING_THRESHOLD` | Lower (e.g. 800) to throttle `collection_cycle` |
| `PIPELINE_REFINEMENT_ANYTIME=false` | Keep refinement GPU work in nightly window |
| `AUTOMATION_DISABLED_SCHEDULES` | Comma list, e.g. `rag_enhancement,graph_connection_distillation,storyline_automation` |

## Feed silencing (warn-then-auto)

| Env | Default | Effect |
|-----|---------|--------|
| `RSS_FEED_SILENCE_ENABLED` | `false` | Enable nightly health evaluation |
| `RSS_FEED_SILENCE_DRY_RUN` | `true` | Log verdicts only; set `false` to apply |
| `RSS_FEED_SILENCE_MIN_QUALITY` | `0.45` | Align with signal gate |
| `RSS_FEED_SILENCE_ZERO_YIELD_DAYS` | `14` | No inserts → warn |
| `RSS_FEED_SILENCE_LOW_SIGNAL_DAYS` | `30` | Articles but none above threshold → warn |
| `RSS_FEED_SILENCE_REVIEW_CYCLES` | `3` | Nightly warns before `is_active=false` |
| `RSS_FEED_SILENCE_GRACE_DAYS` | `21` | New feeds never auto-silenced |

1. Run `rss_feed_yield_report.py --csv /tmp/feeds.csv`
2. Manually Pause dead-weight feeds in RSS UI (target ~40–50 active tier_1/2)
3. Enable `RSS_FEED_SILENCE_ENABLED=true` with `DRY_RUN=true` for one week
4. Set `RSS_FEED_SILENCE_DRY_RUN=false` when warn list looks correct

## Tuning steady state (1–2 weeks)

1. If `intake_first_pass` still climbing: raise `ARTICLE_SIGNAL_FULL_MIN_QUALITY` (0.50–0.55) or trim feeds
2. If ratio &lt; 15%: lower threshold slightly (0.40) or add tier_2 feeds
3. Re-enable optional automation phases one at a time only when `bulk_tier_pending_total` trends down for 7 days

See also: [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md), [AGENTS.md](../AGENTS.md).
