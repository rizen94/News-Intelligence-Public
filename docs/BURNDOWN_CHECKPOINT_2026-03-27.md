# Burndown checkpoint — review later

**Recorded:** 2026-03-27 (America/New_York evening). **Config note:** aggressive burn-down block is in `.env` (see `configs/env.aggressive_burn_down.env`).

## How to compare against this checkpoint

1. **Manual (Monitor)** — Open **Monitor** and compare the tables here to **Backlog status** + automation pending chips (same semantics as below).

2. **New timestamped snapshot (recommended)** — From repo root, API running:
   ```bash
   ./snapshot_backlog_status
   ```
   (Repo root shortcut; same as `bash scripts/snapshot_backlog_status.sh`.)
   Writes `.local/backlog_snapshots/backlog_status_<UTC>.json` and `automation_status_<UTC>.json`, then prints **one timeline table** across up to **four** snapshots (this run plus three prior): same columns for each metric, ordered **oldest → newest**, plus **Δ oldest→now**. First run has no priors yet.

   Re-print the last four snapshots on disk without curling:

   ```bash
   ./scripts/backlog_burndown.sh timeline
   ```

3. **Diff only the two most recent backlog snapshots** (pair mode). **Run from the News Intelligence repo root** (not `~` — paths are relative to that directory).

   ```bash
   cd /path/to/News\ Intelligence   # your clone
   ./scripts/backlog_burndown.sh diff
   ```

   Same thing under the hood as picking the last two `backlog_status_*.json` files in `.local/backlog_snapshots/` (sorted by name) and running `compare_backlog_snapshots.py`.

   Explicit variables (after `cd` to repo root):
   ```bash
   OUT_DIR=".local/backlog_snapshots"
   mapfile -t _bl < <(ls -1 "$OUT_DIR"/backlog_status_*.json 2>/dev/null | sort)
   n="${#_bl[@]}"
   if [[ "$n" -lt 2 ]]; then
     echo "Need at least two files matching $OUT_DIR/backlog_status_*.json (have $n). Run: ./snapshot_backlog_status (repo root)" >&2
     exit 1
   fi
   older="${_bl[$((n - 2))]}"
   newer="${_bl[$((n - 1))]}"
   uv run python scripts/compare_backlog_snapshots.py "$older" "$newer"
   ```

   To compare two **specific** files (from repo root), pass them after `diff`:
   ```bash
   ./scripts/backlog_burndown.sh diff .local/backlog_snapshots/backlog_status_OLD.json .local/backlog_snapshots/backlog_status_NEW.json
   ```
   Shows articles/contexts/entity/storyline backlog and overall ETA/iteration deltas.

4. **Automation queue depth** — Not inside `backlog_status`. Use the paired `automation_status_*.json` from the snapshot script, or:
   ```bash
   curl -sS "http://127.0.0.1:8000/api/system_monitoring/automation/status" | jq '.data.pending_counts'
   ```
   Compare `pending_counts` keys to the table below.

5. **Phase wall-clock** — Long runs are normal for large batches. Check **duration** in DB:
   `public.automation_run_history` (`started_at`, `finished_at`, `phase_name`) or Monitor phase timeline **last run** / productivity scripts in `scripts/SCRIPTS_INDEX.md`.

### Is a 1+ hour phase run “sustainable”?

- **Wall-clock of one invocation** is the wrong single metric. Phases like `claim_extraction`, `claims_to_facts`, `nightly_enrichment_context` are built to **process large slices** per run; with your aggressive `.env`, a run can legitimately exceed an hour while still being healthy.
- **Sustainable** means, over days:
  - **Backlogs you care about** trend **down or flat** (see diff above), not monotonically up.
  - **Inflow vs outflow** on articles/contexts matches what you expect (Monitor **inflow vs outflow** / article trend).
  - **No chronic** DB pool timeouts, Ollama 5xx storms, or GPU OOM — if those appear, reduce concurrency in `.env` before blaming “slow phases.”
- If the **same** phase is always >1h **and** the related **pending count barely moves**, that is a throughput problem (batch size, DB, LLM latency), not just “complexity.”

Quick refresh without saving files:

```bash
curl -sS "http://127.0.0.1:8000/api/system_monitoring/backlog_status" | PYTHONPATH=api uv run python -m json.tool | head -200
```

## Snapshot (API `backlog_status` + automation reasons, ~same time)

### Monitor SQL / ETA rows (from `data`)

| Queue | Backlog | Throughput note | ETA / iterations (then) |
|-------|---------|-----------------|-------------------------|
| Articles (enrich) | **676** | ~144/h avg_4d; **1011** enriched last 1h | ~4.7h · 3 iters · trend **shrinking** |
| Documents (extract) | **5** | 0 last 1h | ~7.4h · 4 iters |
| Contexts (claims) | **30,097** | ~200/h avg_4d; **228** last 1h | ~150.5h · 76 iters |
| Entity profiles | **48,932** / 51,165 | **measured_24h** ~8/h; 192 “nonempty section” updates / 24h | ~6116h · **3059** iters (long pole) |
| Storylines (synthesis) | **225** | 0 last 1h | ~327h · 164 iters |

- **Overall ETA (max queue):** ~**6116.5 h** · **3059** iterations (2h cycles) — driven by entity profile row.
- **Steady state:** **Not yet** — automation backlogs over one-batch; pipeline SQL backlogs present; iterations above baseline.

### Automation pending (representative; full list on Monitor)

| Phase | ~Count (checkpoint) |
|-------|----------------------|
| claims_to_facts | ~864,917 |
| claim_extraction | ~26,599 |
| event_tracking | ~78,970 |
| entity_profile_build | ~48,907 |
| storyline_discovery | ~44,339 |
| entity_extraction | ~9,127 |
| event_extraction | ~16,058 |
| proactive_detection | ~8,677 |
| content_enrichment | **621** |
| context_sync | ~1,230 |
| content_refinement_queue | **117** |
| nightly_enrichment_context | ~2,132 |

### Compared to earlier same-day paste (directional)

- **Improved:** articles backlog, `content_enrichment`, `claims_to_facts`, `storyline_discovery`, `content_refinement_queue`, `nightly_enrichment_context`.
- **Roughly flat:** contexts backlog, entity profile backlog, storyline synthesis backlog, documents.
- **Mixed / up:** `claim_extraction`, `context_sync`, some extraction/metadata counts.

## Next check-in

1. Re-run the curl above (or Monitor).
2. Compare tables: same keys, note deltas.
3. If pool/Ollama errors appear, consider trimming concurrency in `.env` before removing the whole aggressive block.
