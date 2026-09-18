# Stale duplicate copies (archived 2026-09)

Second copies of files whose live version lives elsewhere. Each one was already behind its
authoritative counterpart, so agents and reviewers grepping the repo were as likely to land on
the stale text as the current one.

| Archived here | Live version |
|---------------|--------------|
| `PIPELINE_AND_AUTOMATION.root-copy.md` | `docs/PIPELINE_AND_AUTOMATION.md` (newer) |
| `PIPELINE_QUALITY_AND_IDEMPOTENCY_REVIEW_CHECKLIST.root-copy.md` | `docs/PIPELINE_QUALITY_AND_IDEMPOTENCY_REVIEW_CHECKLIST.md` |
| `ASSEMBLY_MODEL.api-services-copy.md` | `docs/ASSEMBLY_MODEL.md` (newer) |
| `dot-version.8.0.0.txt` | repo-root `VERSION` — the version SSOT per `AGENTS.md`. The old `.version` still said `8.0.0` against `VERSION` `10.1.0`, and its only reader was the already-archived `docs/archive/development_ai_session_tooling/.../version_manager.py`. |
| `entities.json` | No reader anywhere in the repo; a stray extraction artifact. |

`my_pihole.txt` was untracked in the same pass rather than archived: `.gitignore` already lists it
as machine-local state, so it should never have been committed. The file stays on disk.
