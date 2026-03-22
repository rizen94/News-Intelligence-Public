# Archived frontend trees

**`_archived_interface/`** — Pre–TypeScript-migration UI (pages, DomainLayout, etc.). **Not imported** by `App.tsx`; excluded from `tsc`/ESLint/Prettier via `web/tsconfig.json` and ignore files.

Restore selectively only when mining old JSX/UX; prefer extending `web/src/pages/` and `web/src/components/`.
