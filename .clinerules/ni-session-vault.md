# Session memory — vault first, self-compress (Plan + Act)

Cline **`useAutoCondense` is off** on purpose. **You** compress: write durable state to Obsidian, then keep chat thin.

Applies in **Plan** and **Act** equally.

---

## Vault MCP (`obsidian-vault`)

| Tool | Use |
|------|-----|
| **`vault_read_note`** | Start / resume / after any compact or stall |
| **`vault_append_note`** | Every material finding and before context gets heavy |
| **`vault_write_note`** | Create handoff once per job (then append only) |

Paths are vault-relative (Life OS vault on NAS), e.g. `00_Inbox/handoffs/2026-11-09-pipeline-status.md`.

Template: vault `40_Reference/cline-handoff-template.md`.

---

## One handoff note per job (mandatory)

At task start (or first turn on a multi-step bug):

1. **`vault_write_note`** or append if file exists: `00_Inbox/handoffs/YYYY-MM-DD-<slug>.md`
2. Top: **verbatim user goal** — never let later summaries replace it
3. Mirror a checkbox on `60_Life/Tasks.md` when homelab Life OS is in scope

**Slug** = short topic (`pipeline-automation-status`, `pending-items-triage`).

---

## When to `vault_append_note` (do not wait for user)

| Trigger | Append what |
|---------|----------------|
| After **each proven** SQL result (counts, sample rows) | One-line query + numbers |
| After **code root cause** identified | Path, function, line-level fact |
| After **≥3 tool rounds** in one investigation arc | Rolling summary + open questions |
| **Before** Plan → Act switch | Approved plan + files to touch |
| **Before** `./scripts/deploy_to_widow.sh` | Commit SHA + why deploy |
| **After** deploy / fix | Status block from `ni-verify-completion.md` |
| Context feels **large** (many tool JSON blobs in thread) or responses **slow / stall** | **Checkpoint now** — then self-compress (below) |

**Never** paste secrets, `.env` values, or full tool payloads into the vault — pointers only.

---

## Self-compress (after vault write)

Right after `vault_append_note`, shrink what you say in chat:

1. **Do not** re-print full MCP tool outputs, long SQL tables, or stack traces in chat if they are in the vault.
2. Reply with **≤10 bullets**: goal, current hypothesis, last proof, next tool, **vault path**.
3. Continue working — **re-read the handoff** with `vault_read_note` at the start of the next turn if the thread was long or the UI lagged.

Chat is scratch space; the vault is **source of truth** when context hits ~32k.

---

## Resume after freeze / compact / new session

1. `vault_read_note` handoff path (and `60_Life/Tasks.md` if needed)
2. One sentence: where you left off
3. **Do not** re-run discovery already recorded in the handoff unless verifying drift

---

## Context diet (both modes)

| Do | Avoid |
|----|--------|
| Narrow `search` / read one handler file | `pack_codebase` / huge @-attachments unless user asked |
| postgres-mcp with `LIMIT` | Pasting migration dirs into chat |
| Point vault at evidence | Repeating the same SQL in every turn |

If **`Project Context Protocol.md`** conflicts with this file on packing — **this file wins** for long NI sessions.

---

## Plan vs Act (same vault)

| Mode | Vault emphasis |
|------|------------------|
| **Plan** | Evidence log, structured plan steps, SQL proof — no deploy commands |
| **Act** | Diff paths, commands run, deploy exit codes, re-check SQL |

Same handoff file for both modes on one job.
