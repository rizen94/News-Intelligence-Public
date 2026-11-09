# News Intelligence — implement & deploy when instructed

Read **`ni-plan-vs-act.md`**, **`ni-deep-investigation.md`**, **`ni-deploy.md`**, **`ni-verify-completion.md`**.

## Capabilities (no refusal boilerplate)

You **can** use **editor**, **run_commands**, **git**, and **SSH** (Widow `192.168.93.101`) in this IDE when the user authorized work.

**Forbidden responses:**

- “I cannot execute deployment scripts”
- “I don't have access to production systems”
- “My role is to provide recommendations only”

When deploy is authorized → run **`./scripts/deploy_to_widow.sh`** and report results.

## Implement triggers

*implement*, *apply*, *fix it*, *ship*, *deploy*, *push to Widow*, *do it*, *go ahead*.

- Use tools through completion — no stopping at instructions.
- Do not re-ask “should I proceed?” after deploy/implement was already authorized in-thread.

**One-shot confirm** only for: destructive SQL, force-push, secret rotation — not for normal `deploy_to_widow.sh`.

## Verify

See **`ni-verify-completion.md`** — no “fixed” without diff + re-check SQL; no “deployed” without script success + BUILD_INFO/SQL proof.
