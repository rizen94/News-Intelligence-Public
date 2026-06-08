# Project Context Protocol

## Before Making Changes
When starting any task that involves modifying code, understanding architecture, or debugging:

1. **First, pack the codebase** using the repomix MCP tool's `pack_codebase` with:
   - directory: /home/pete/Documents/projects/News Intelligence
   - compress: true
   - includePatterns: "**/*.py,**/*.yaml,**/*.yml,docker-compose*.yml"
   - ignorePatterns: "scripts/ni_review/**,api/database/migrations/archive/**,docs/archive/**,diagnostics/**,**/__pycache__/**"

2. **Then search before editing.** Before modifying any file, use `grep_repomix_output` to find:
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
- Never modify a file without first checking what depends on it via grep_repomix_output
- If a task is ambiguous, pack and search before asking me clarifying questions
- When you find circular imports or tight coupling, flag it