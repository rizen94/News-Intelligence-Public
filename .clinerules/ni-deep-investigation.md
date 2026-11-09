# News Intelligence — deep investigation (required)

Shallow answers are **wrong**. High-level file lists, migration filenames, schema guesses, or “table probably has X” **do not count** as investigation.

**Cline must use** `postgres-mcp` tools and **read deployed code paths** before recommending or implementing changes.

**`lab-backbone` (qwen3-coder)** has **no thinking mode** in Ollama — only normal reply text + tools. Before the first tool call in a turn, write a **short hypothesis** (2–4 sentences: what you will check and why). That is deliberate reasoning, not a `` block.

SoT SQL patterns: `docs/AGENT_DOMAIN_DB_INSIGHTS.md` (repo). DB explorer phases: HomeLab `docs/prompts/news-db-explorer-system.md` (copy workflow below).

---

## Evidence ladder (complete in order; skip only what the user scoped out)

### A. Database (Widow `news_intel` via `postgres-mcp` only — not PopOS `:15432`)

| Step | Tool | Requirement |
|------|------|----------------|
| 1 | `list_schemas` | Name schemas you will query |
| 2 | `list_objects` | Per schema you cite |
| 3 | `get_object_details` | **Before** any non-trivial `execute_sql` on a table |
| 4 | `execute_sql` | Bounded `SELECT` only (`LIMIT` ≤50); **row counts**, **samples**, **joins** that prove the claim |

**Never** conclude from:

- Migration numbers alone
- Duplicate table names across `public` / `infrastructure` / `pipeline` without **counts per schema**
- Column names on `storylines` without checking `ml_processing_status`, queues, and `intelligence.*` (see anti-patterns below)

**Start domain work with:**

```sql
SELECT domain_key, schema_name, name, is_active
FROM public.domains
ORDER BY display_order, domain_key;
```

**Pipeline / automation claims must hit at least one of:**

- `public.automation_run_history` (recent rows, phase, pass/fail)
- `pipeline.pipeline_traces` or `public.pipeline_*` / `infrastructure.pipeline_*` with `get_object_details` first
- `intelligence.content_refinement_queue` pending vs done
- Article/storyline tables with real `WHERE` filters (domain schema, dates)

### B. Code (repo + deployed path)

| Step | Action |
|------|--------|
| 1 | `grep` / search **symbol** (function, class, route, env var, phase name) |
| 2 | **Read the implementing file** (not just `models.py` header or `__init__.py`) |
| 3 | **Read one caller and one callee** when tracing pipeline/automation |
| 4 | For API behavior: open the **route handler** and the **service** it calls |
| 5 | For workers: find **systemd unit** or **AutomationManager** registration and read that module |

**Repo roots:**

| Tree | Path |
|------|------|
| Dev (PopOS) | `~/Documents/projects/News Intelligence/` |
| Prod on Widow | `/opt/news-intelligence/` (compare only when user asks prod vs dev) |

**Deployed check (read-only SSH):**

```bash
ssh pete@192.168.93.101 'systemctl is-active news-intelligence-api-public.service; readlink -f /opt/news-intelligence 2>/dev/null; git -C /home/pete/Documents/projects/News\ Intelligence rev-parse --short HEAD 2>/dev/null'
```

Do **not** paste passwords in chat; use env / Infisical names only.

### C. Synthesis (before implement)

In chat or handoff, include **Evidence:** bullets with:

- SQL you ran (one line each) + **result shape** (counts, not vague “many rows”)
- File paths + **function names** that own the behavior
- **Dev vs prod** if they differ

---

## Storyline / pipeline anti-patterns (do not shallow-declare)

| Wrong jump | Check instead |
|------------|----------------|
| “NER broken” from `key_entities` | `{domain}.story_entity_index`, `article_entities` |
| “Pipeline stalled” from one status column | `ml_processing_status`, refinement queue, `automation_run_history` |
| “No timeline data” | `public.chronological_events` (not legacy per-domain `timeline_events`) |
| “Duplicate tables = broken” | `get_object_details` + `COUNT(*)` **per schema** for each duplicate name |

---

## Depth vs implement overlay

From `ni-implement.md`: **investigate deeply first**; when the user says **implement**, apply the fix using evidence from **A + B**, not a plan built on metadata alone.
