# Ollama Routing Policy

> **Where work goes and why.** Maps every invocation kind to a host (Widow CPU / PopOS GPU / Dockside embeds), the model selected, and the configuration knobs that control the decision.

**Source files:** `api/shared/services/ollama_model_policy.py`, `api/shared/services/llm_service.py`, `api/config/runtime.py`.

---

## 1. Device Map

| Device | Host (default) | Hardware | Used for |
|--------|----------------|----------|----------|
| **Widow** (generate host, CPU lane) | `http://localhost:11434` via `OLLAMA_HOST` | GTX 1080 (8 GB VRAM) | Extraction, fast-simple, fallback default |
| **PopOS** (GPU lane) | `http://192.168.93.99:11434` via `OLLAMA_POP_OS_HOST` | RTX 5090 (32 GB VRAM) | Synthesis, finish, briefing lead, finance high-quality |
| **Dockside** (embeds appliance) | `http://192.168.93.95:11434` or tunnel `http://127.0.0.1:11435` via `OLLAMA_EMBEDDINGS_HOST` | Dedicated embeds hardware | Embeddings only (separate circuit breaker) |

---

## 2. Lane Routing (`_execution_lane_for_kind`)

**Gate:** `OLLAMA_DUAL_HOST_ROUTING_ENABLED` defaults to `true` in `config/runtime.py:118`. Set to `false` to collapse all lanes to Widow.

### GPU lane → PopOS

| Invocation kind | Model tag (default) |
|-----------------|---------------------|
| `LONG_SYNTHESIS` | `high` / `secondary` |
| `STORYLINE_NARRATIVE_FINISH` | `finish` / `finisher` |
| `BRIEFING_LEAD` | `high` / `secondary` |
| `FINANCE_GENERATION_HIGH` | `high` / `secondary` |
| `INTERACTIVE_SUMMARY` | `high` / `secondary` |

### CPU lane → Widow

| Invocation kind | Model tag (default) |
|-----------------|---------------------|
| `STRUCTURED_EXTRACTION` | `extract` / `extraction` (unless `BULK_USE_POPOS_EXTRACTION=1`) |
| `FAST_SIMPLE` | `low` / `phi` (unless `OLLAMA_USE_PHI_FOR_FAST_SIMPLE=0`) |
| `REAL_TIME_UI` | `default` / `primary` |
| `BACKGROUND_BATCH` | `high`/`DEFAULT` depending on prompt size (≥12 k chars → high; else default) |
| All other / unmatched | `default` / `primary` |

---

## 3. Model Resolution Chain

Each model tag maps to an env var chain + fallback tag:

| Tag keys | Env vars checked (in order) | Fallback tag |
|----------|-----------------------------|--------------|
| `low`, `phi` | `OLLAMA_MODEL_PHI` | `phi3.5:latest` |
| `default`, `primary` | `OLLAMA_MODEL_PRIMARY` | `llama3.1:8b` |
| `high`, `secondary` | `OLLAMA_MODEL_SECONDARY` | `mistral-nemo:12b` |
| `extract`, `extraction` | `BULK_EXTRACTION_MODEL`, `OLLAMA_MODEL_EXTRACTION` | `qwen3.6:latest` |
| `finish`, `finisher` | `OLLAMA_NARRATIVE_FINISHER_MODEL`, `OLLAMA_OPTIONAL_QUALITY_MODEL` | `qwen3.6:latest` |

---

## 4. 70B Override

Any model name containing `:70b` (or the sentinel `ModelType.LLAMA_70B`) **always goes to PopOS**, bypassing lane logic entirely. This is a hardcoded check in `_resolve_sync_execution_target`.

---

## 5. Embeddings Path

| Setting | Value / behavior |
|---------|------------------|
| Env var | `OLLAMA_EMBEDDINGS_HOST` (Dockside LAN or Widow tunnel) |
| Circuit breaker key | `ollama_embeddings` — **separate** from `OLLAMA_CB_KEYS` |
| Fallback when unset | Silently falls back to CPU host (`OLLAMA_HOST`) in `_embedding_target()` — works but bypasses Dockside intent |

---

## 6. Context / Token Budgets by Lane

| Lane | `num_predict` (tokens) | `num_ctx` (window) | Temperature |
|------|------------------------|--------------------|-------------|
| Extraction | `max(900×batch, base)` — default base 4096; context capped to 8192 | Default 8192 via `OLLAMA_EXTRACTION_NUM_CTX` | 0.15 (low) |
| Narrative finish | 2000 | Default 8192 via `OLLAMA_NARRATIVE_FINISHER_NUM_CTX`; cap 16384 | 0.7 |
| Interactive summary / briefing lead / background batch / default | 800 | None (uses model default) | 0.7 |
| Finance generation high | 1200 | None | 0.7 |
| Fast simple | 2048 | None | 0.7 |
| Real-time UI | 2048 | None | 0.7 |

---

## 7. Model Residency (keep_alive)

UI lanes (`REAL_TIME_UI`, `INTERACTIVE_SUMMARY`) keep models resident for **2 minutes** via `OLLAMA_UI_KEEP_ALIVE`. All other automation uses **2 minutes** via `OLLAMA_AUTOMATION_KEEP_ALIVE` (default was historically 30 min; reduced to conserve VRAM).

---

## 8. Configuration Summary

All runtime config flows through `api/config/runtime.py`:

| Env var | Default | Role |
|---------|---------|------|
| `OLLAMA_HOST` | `http://localhost:11434` | Widow (generate host) |
| `OLLAMA_POP_OS_HOST` | `http://192.168.93.99:11434` | PopOS (GPU host) |
| `OLLAMA_EMBEDDINGS_HOST` | *(none)* | Dockside (embeds appliance) |
| `OLLAMA_DUAL_HOST_ROUTING_ENABLED` | `true` | Enable/disable dual-host split |
| `OLLAMA_MODEL_PRIMARY` | `llama3.1:8b` | Default/primary model tag |
| `OLLAMA_MODEL_SECONDARY` | `mistral-nemo:12b` | Secondary/high-quality model tag |
| `OLLAMA_MODEL_PHI` | `phi3.5:latest` | Fast/simple model tag |
| `BULK_EXTRACTION_MODEL` or `OLLAMA_MODEL_EXTRACTION` | `qwen3.6:latest` | Extraction model tag |
| `OLLAMA_NARRATIVE_FINISHER_MODEL` or `OLLAMA_OPTIONAL_QUALITY_MODEL` | `qwen3.6:latest` | Finish model tag |
| `BULK_USE_POPOS_EXTRACTION` | `false` | Override extraction to PopOS |
| `OLLAMA_USE_PHI_FOR_FAST_SIMPLE` | `true` | Use Phi for fast/simple lanes |
