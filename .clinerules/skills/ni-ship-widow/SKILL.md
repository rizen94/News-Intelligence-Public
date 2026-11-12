---
name: ni-ship-widow
description: >-
  Deploy News Intelligence to Widow production and verify done criteria.
  Use when user authorizes prod deploy, deploy_to_widow.sh, or asks if a fix
  is live on Widow — Act mode only.
---

# Ship to Widow (NI production)

**Act mode** — only when the user **authorizes** Widow / production deploy.

## Before deploy

1. Local diff exists on the correct modules (not repo-root one-off `fix_*.py` scripts).
2. Relevant tests or smoke checks if the change touches API wiring.
3. Handoff notes what will change in prod.

## Deploy

```bash
./scripts/deploy_to_widow.sh
```

Do not refuse with "I cannot deploy" when the user already authorized Widow.

## After deploy (required for "done")

1. Re-run **the same SQL or health checks** from `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` §2 that showed the bug.
2. `vault_append_note` — deploy command, exit code, post-check result (no secrets).
3. Chat: short bullets only — *fixed* means deploy success **and** §2 re-check, not local edits alone.

## Not done

- INSERT seed data to "fill" an orphan table without wiring writers in `api/`.
- Vault/MemPalace entry celebrating success without deploy exit code + §2 proof.
