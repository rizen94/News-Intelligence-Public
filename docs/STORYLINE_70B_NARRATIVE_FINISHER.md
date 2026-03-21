# Storyline narrative finisher (~70B)

## Role

**Llama 3.1 8B** and **Mistral 7B** own the **high-volume** path: summaries, structured extraction, events, claims, context sync, draft storyline text, and routine review.

**The narrative finisher** (`settings.NARRATIVE_FINISHER_MODEL`, default **`llama3.1:70b`**) is the **final editor and reviewer** for **storyline-level** intelligence:

- Consumes **aggregated outputs** from the lower tier (article summaries, entities, contexts, timeline notes, existing storyline copy, linked events).
- Produces a **durable, cleaned narrative** meant to be a **permanent fixture** for that storyline — not rewritten from scratch every time a new article arrives.
- **Integrates** new evidence over time: suggests **new contexts**, **entities**, and **narrative threads** worth attaching; flags **stale or redundant** material to drop or soften so the story stays coherent.
- Runs **infrequently** compared to 8B/Mistral (scheduled or on-demand), so GPU and backlog stay healthy.

This is the **only** invocation kind that routes to the finisher model: `InvocationKind.STORYLINE_NARRATIVE_FINISH` → `ModelType.LLAMA_70B` (see `api/shared/services/ollama_model_policy.py`).

## What “permanent fixture” means (product)

- **Baseline narrative** (title, summary, editorial description, key beats) is **refined and stored** after a finisher pass.
- **New articles** still flow through 8B/Mistral as today; periodically (or when thresholds hit), the **finisher** re-reads the **whole storyline bundle** and **updates** the stored narrative and “canonical” storyline metadata — merge, prune, extend — rather than replacing the storyline id or throwing away history.
- **Audit trail:** keep prior finisher versions if needed (DB design TBD); at minimum store `last_narrative_finish_at` and model tag.

## Inputs (conceptual)

Pack into the finisher prompt (bounded by context window):

1. **Storyline record** — title, status, existing long-form text fields, domain.
2. **Article set** — titles, dates, short summaries or key sentences (from 8B path), not necessarily full bodies.
3. **Entities / contexts** — salient names and context labels the pipeline already produced.
4. **Timeline / events** — optional bullet list from `chronological_events` or domain events.
5. **Instructions** — JSON or structured output schema for: refined narrative, suggested additions, suggested removals, open questions.

## Outputs (conceptual)

- **Refined narrative** (markdown or plain text) for UI and downstream RAG.
- **Structured deltas** (machine-readable): `suggested_new_entities`, `suggested_new_context_links`, `sections_to_deprecate`, `confidence_notes`.
- **Persistence** — implement in `storyline_narrative_finisher_service` + migrations (not all wired yet).

## Configuration

| Env / setting | Purpose |
|---------------|---------|
| `OLLAMA_NARRATIVE_FINISHER_MODEL` | Ollama tag for finisher (default `llama3.1:70b`). |
| `OLLAMA_PULL_NARRATIVE_FINISHER` | If `true`, include finisher in `refresh_ollama_models.py` (large pull). |
| `OLLAMA_EXTRA_PULL_MODELS` | Comma-separated; can still add `llama3.1:70b` if you prefer not to use the flag above. |

## Code entry points

| Piece | Path |
|-------|------|
| Policy | `api/shared/services/ollama_model_policy.py` — `STORYLINE_NARRATIVE_FINISH` |
| Caller | `api/shared/services/ollama_model_caller.py` — `generate(..., kind=InvocationKind.STORYLINE_NARRATIVE_FINISH)` |
| Service (skeleton) | `api/services/storyline_narrative_finisher_service.py` |
| Model enum | `api/shared/services/llm_service.py` — `ModelType.LLAMA_70B` |

## Implementation checklist (engineering)

1. **Load bundle** — `load_finisher_bundle_from_db` + `run_narrative_finish_from_db` in `api/services/storyline_narrative_finisher_service.py` (storyline row, linked articles, top entities, optional `public.chronological_events`).
2. **Prompt + schema** — finisher prompt in service module; `parse_finisher_response` parses JSON after `---JSON---`.
3. **Persist** — migration `181_content_refinement_queue_and_storyline_narratives.sql`: `canonical_narrative`, `narrative_finisher_*`, timeline narrative text columns; `persist_narrative_finish_to_db` in `storyline_narrative_finisher_service.py`.
4. **Scheduler** — automation task `content_refinement_queue` (see `automation_manager`); cap finisher jobs via `CONTENT_REFINEMENT_MAX_FINISHER_JOBS_PER_CYCLE`. API: `POST /api/{domain}/storylines/{id}/refinement_jobs` with `job_type` (`narrative_finisher`, `comprehensive_rag`, `timeline_narrative_*`).
5. **Guardrails** — skip if no new articles since last finish; cap prompt size; timeout > 8B default.

## Related docs

- [SETUP_ENV_AND_RUNTIME.md](./SETUP_ENV_AND_RUNTIME.md) — Ollama pull / refresh; archived detail in `_archive/consolidated/OLLAMA_SETUP.md`.
- `AGENTS.md` — Ollama / narrative finisher bullet.
- `api/shared/services/ollama_model_policy.py` — routing rules.
