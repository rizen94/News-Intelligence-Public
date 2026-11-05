# Automation Pitfalls & Fixes — News Intelligence System

> **Purpose:** Document recurring automation defects, their root causes, and how they were fixed so patterns are not replicated. Entries are ordered by date (newest first).

---

## 2026-10-27 — Backpressure: linear vs exponential retry spacing

| Field | Detail |
|-------|--------|
| **File** | `api/services/phase_retry_silence_service.py` → `backoff_seconds_for_retry()` |
| **Bug class** | Aggressive linear retries under sustained backpressure |
| **Symptom** | Transient failures (DB pool exhaustion, Ollama GPU out-of-memory) caused retry storms at fixed 60-second intervals (`60×n`, capped at 300s). Each retry hammered a still-recovering system; the phase would fail again and repeat until auto-silence threshold was hit (~3–5 wasted retries over ~150s). |
| **Root cause** | Linear backoff assumes failures resolve linearly. In practice, pool drain and model warm-up are *non-linear* — a recovered PG connection takes an unpredictable burst of new requests to stabilize; Ollama needs the VRAM cycle to complete before accepting more batches. |
| **Fix** | Switched to exponential spacing: `min(base ** max(1, retry_count), cap)`. With defaults (base=60, cap=300): retry 0→60 s, retry 1+→300 s. The cap means after the first long pause the system has time to actually recover; remaining retries are either already fine or worth silencing. |
| **Rule** | **Never use linear backoff for infrastructure dependencies (DB, LLM, HTTP).** Always exponential with a hard cap. If you need finer granularity later, use jitter + exponential rather than linear. |

---

## 2026-10-27 — depends_on mutation across schedule toggle cycles

| Field | Detail |
|-------|--------|
| **File** | `api/services/automation_manager.py` → `_apply_automation_disabled_schedules()` |
| **Bug class** | Irreversible state mutation of dependency lists |
| **Symptom** | When a schedule was disabled (via `AUTOMATION_DISABLED_SCHEDULES` or remote ownership), its name was stripped from all dependents' `depends_on` lists. If that schedule later came back online, the dependent's `depends_on` remained corrupted — the dependency was gone permanently in memory. The phase would run **without** its prerequisite, producing stale/incomplete output. |
| **Root cause** | `depends_on` is both *metadata* (what the YAML says) and *runtime state* (what's currently stripped). Stripping mutated the live object; there was no baseline to restore from. Subsequent toggles only compounded the erosion — each disabled schedule stripped another name, but re-enabling never restored any. |
| **Fix** | Snapshot the original `depends_on` at first invocation: `self.__dict__[f"_orig_{sched_name}_deps"] = list(sched.get("depends_on") or [])`. All subsequent filter computations use this immutable baseline, so toggling a disabled schedule on/off is idempotent. Dependencies are always restored from the YAML truth. |
| **Rule** | **Never mutate shared config objects in-place during runtime.** Always keep an immutable snapshot of original state and recompute derived values from that baseline each cycle. Use `self.__dict__` for per-instance snapshots, not module-level globals. |

---

## 2026-10-27 — Zombie auto-silence loop after phase recovery

| Field | Detail |
|-------|--------|
| **File** | `api/services/phase_retry_silence_service.py` → `apply_auto_silence_from_health()` + `_auto_silence_cooldown_elapsed()` |
| **Bug class** | Infinite silence/lift cycle for phases that briefly recover then immediately fail |
| **Symptom** | Phase health flips from `failing` to something else (or stays failing but streak resets) → auto-silence is lifted and streak reset to 0 → next health tick sees the same failure → streak bumps back to threshold within seconds → phase re-silenced. The cycle repeats every ~30s with no human intervention ever resolving it. |
| **Root cause** | `_record_lift` resets `failing_streak` to 0, but run history still contains old failure rows. The health assessment picks those up immediately; the streak hits threshold in the next tick. No temporal separation between "lift" and "re-evaluate." |
| **Fix** | Added a 10-minute post-lift cooldown (`_DEFAULT_AUTO_SILENCE_COOLDOWN_SEC = 600`). After `_record_lift`, `last_lifted_at` is recorded; the cooldown function reads it from `phase_silence_state.cleared_at` and blocks re-silencing for that window. If the phase genuinely recovers within those 10 minutes, streaks stay healthy. If it fails again after the window, auto-silence triggers with full context of the new failure pattern. |
| **Rule** | **Any state transition that resets a counter/accumulator needs a temporal guard against immediate reversal.** Cooldown windows break cycles where the system oscillates between two states faster than resolution can occur. |

---

## Pre-Flight Checklist (for future automation changes)

When modifying scheduling, retry, or auto-silence logic, verify:

1. **Immutability:** Are you mutating any shared config objects (`schedules`, `depends_on`, domain lists)? If so, snapshot the original and recompute from baseline each cycle.
2. **Temporal safety:** Does a state reset (streak → 0, counter → N) have a minimum time before it can be re-triggered? Without this, oscillation is guaranteed under sustained failure conditions.
3. **Backoff strategy:** Is your retry spacing exponential with a cap? Linear backoff on infrastructure failures will amplify the problem.
4. **Idempotency of toggles:** Can you disable and re-enable a schedule any number of times without corrupting `depends_on` or other derived state?

---

## See Also

- [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) — scheduling model reference
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — operational diagnostics
- [WIDOW_BOOT_RESILIENCE.md](WIDOW_BOOT_RESILIENCE.md) — service startup ordering
