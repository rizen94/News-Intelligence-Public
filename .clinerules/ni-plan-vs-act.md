# News Intelligence — Plan vs Act (shared tools & style)

Cline **Plan** → `lab-backbone-reason:latest` (qwen3.6). **Act** → `lab-backbone:latest` (qwen3-coder).  
**Same** investigation tools, SQL discipline, paths, and code conventions in both modes — only **permissions** differ.

---

## Shared (Plan and Act)

### MCP servers (use connected IDs only)

| Server | When | Tools (exact names) |
|--------|------|---------------------|
| **`postgres-mcp`** | NI live DB (Widow `news_intel`) | `list_schemas` → `list_objects` → `get_object_details` → `execute_sql` |
| **`homelab-env-manager`** | ports/compose (homelab only) | `hem_*` as listed in MCP panel |
| **`mempalace`** | homelab recall | `mempalace_search`, `mempalace_get_drawer`, … (never `query_memories`) |
| **`obsidian-vault`** | Life OS / handoffs | `vault_read_note`, `vault_append_note`, … |

Do **not** invent server names (`news-intel-server`, `mempalace-server`).

### Tool-calling shape (both models)

- Use Cline **native `tool_use`** blocks — **never** paste faux JSON like `{"name":"plan_code_change",...}` as plain text.
- **postgres-mcp:** always schema-qualified tables (`pipeline.pipeline_automation_status`), `SELECT` only unless user authorized writes; **`LIMIT ≤ 50`**.
- **Evidence ladder:** same order as `ni-deep-investigation.md` in both modes before claiming root cause.
- **Paths:** dev tree `~/Documents/projects/news_intelligence/`; prod read-only compare `/opt/news-intelligence/` on Widow when relevant.
- **Hypothesis:** short visible paragraph before the first tool batch in a turn (required on coder Act; good practice on Plan too).

### Code style (when editing — Act; when citing in plans — Plan)

| Area | Convention |
|------|------------|
| **Python** | Match the target file: imports, async/sync, logging, existing patterns — no drive-by refactors |
| **SQL in chat** | One statement per snippet; show schema.table; note row counts in prose |
| **Config / env** | Cite Infisical **key names** only, never values |
| **Tests** | Prefer existing `pytest` layout; run smallest test that proves the fix |
| **Status language** | `ni-verify-completion.md` — no “fixed” without re-check |

---

## Plan mode only

**Goal:** investigate, structure work, approve changes — **not** ship code or prod.

| Allowed | Not allowed (switch to Act or get user approval) |
|---------|---------------------------------------------------|
| `postgres-mcp` read tools, `search` / read file tools | `write_to_file`, patch apply, destructive SQL |
| Cline **`plan_code_change`** as real **`tool_use`** (structured plan) | Narrative-only “plans” with no `plan_code_change` tool |
| `ask_question` when **one** real fork blocks the plan (max 1 per turn) | `ask_question` loops instead of investigating |
| Optional `mempalace_search` / vault **read** for context | Widow deploy, `systemctl restart`, migration **APPLY** |

**Plan output:** steps tied to **files/functions** you will touch in Act + SQL re-checks from verify-completion.

---

## Act mode only

**Goal:** implement and prove — per `ni-implement.md`.

| Required when user authorized implement | Prod (only if user named Widow/deploy) |
|----------------------------------------|----------------------------------------|
| `editor` / patches until acceptance criteria met | Documented deploy path + SSH/SQL proof |
| Re-run failing SQL/test after edit | No “deployed” without post-check |

**Thinking:** qwen3-coder has **no** hidden thinking channel — reason in **visible text**, then tools.

---

## Mode handoff

When user approves Plan → Act:

1. **`vault_append_note`** — plan + evidence + files (see **`ni-session-vault.md`**)
2. **Self-compress** chat to bullets + vault path
3. Continue from the approved plan; do not re-ask to proceed

Re-use the same SQL and file paths from Plan; change **status** only after verify gates pass.

## Session size (Plan + Act)

Follow **`ni-session-vault.md`**: checkpoint to vault before context (~32k) stalls the run. Plan and Act use the **same handoff file** on one job.
