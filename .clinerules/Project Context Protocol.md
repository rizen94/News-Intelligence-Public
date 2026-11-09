# Project Context Protocol

## Before Making Changes
When starting any task that involves modifying code, understanding architecture, or debugging:

0. **Session vault** — open or create `00_Inbox/handoffs/YYYY-MM-DD-<slug>.md`; append findings as you go (**`ni-session-vault.md`**). Do not balloon chat context.

1. **Search before editing** (default). Use Cline **search/grep** on `~/Documents/projects/news_intelligence`. **Do not** run `pack_codebase` unless the user asks or the symbol is unreachable after targeted search — packing blows the context window.

2. **If you already packed**, use `grep_repomix_output` to find:
   - All imports of the module you're about to change
   - All files that call functions you're modifying
   - Related route definitions, service classes, or database models

3. **Understand the dependency chain.** If you're changing a function signature, grep for that function name across the packed output to find every caller.

## Architecture Awareness
This is a Python/FastAPI project with domain-based organization. Key patterns:
- Routes live in `api/domains/{domain}/routes/`
- Services live in `api/services/`
- Database models and migrations in `api/database/`
- Docker orchestration via docker-compose files at project root

## Rules
- Never modify a file without checking callers (search/grep or repomix grep if pack already exists)
- If a task is ambiguous, **vault_append_note** the question and use postgres-mcp + one file read — avoid pack-first
- When you find circular imports or tight coupling, flag it