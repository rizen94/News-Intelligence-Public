# News Intelligence — Cline **Plan mode**

Load with **`ni-agent.md`**. Hooks set **`NI_CLINE_MODE: plan`** on Plan tasks — that flag overrides any Act text in older messages.

---

## Permissions (Plan only)

- Investigate; **`plan_code_change`** as real tool use.
- **No** file writes, **no** `run_command` / shell, **no** `./scripts/deploy_to_widow.sh`, **no** prod restarts.
- End with **`ni-plan-handoff`** (required sections in skill).

## Do not

- Say “switch to Act” without a complete handoff.
- Claim *fixed*, *shipped*, or *deployed*.
- Use **`ni-ship-widow`**.

## Pipeline

**Reader/feed/RSS/product** → skill **`ni-golden-trace`**: pick golden `article_id`, name **first broken stage** in Diagnosis; approved steps target that stage only.

Skill **`ni-pipeline-debug`** through step 5 (SQL/log evidence). Step 6 = **`plan_code_change`** only — not `replace_in_file` / editor.

Handoff must include: `golden_article_id`, stage 1–5 table (pass/fail), no “recommendations only” without stage N.
