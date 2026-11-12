---
name: ni-plan-handoff
description: >-
  End of Cline Plan mode for News Intelligence — vault handoff sections, evidence,
  approved steps before Act. Use when finishing investigation, switching Plan to Act,
  or user asks for a handoff packet.
---

# Plan → Act handoff (NI)

**Plan mode** — complete before the user switches to Act or before ending a Plan session.

## Handoff file

Path: `00_Inbox/handoffs/YYYY-MM-DD-<slug>.md` (create or append).

### Required sections

1. **Goal** — user request verbatim at top.
2. **Evidence** — SQL row samples, log lines, file paths opened **for a reason** (not dumps).
3. **Diagnosis** — what is broken vs symptom; cite §2 ladder step that proved it.
4. **Approved plan** — numbered steps Act should execute (files/modules to touch).
5. **Out of scope** — what you are explicitly not doing yet.

## Plan discipline

- Use **`plan_code_change`** as a real tool — not JSON in chat.
- No file writes, no `./scripts/deploy_to_widow.sh`, no prod restarts in Plan.
- Same retrieval order as skill **ni-pipeline-debug** before proposing code changes.

## Act pickup

When the user approves Act: read this handoff first — do not re-ask permission. One handoff per job.

## Vault

`vault_append_note` after each proved milestone; point user to handoff path in one line.
