---
name: Frontend — TypeScript and web conventions
description: React/Vite/MUI patterns for web/src
alwaysApply: false
globs:
  - "web/**/*.ts"
  - "web/**/*.tsx"
---

# Frontend (`web/`)

- **New code:** TypeScript only — **`.tsx`** for components, **`.ts`** for logic.
- **Logging:** use **`Logger`** from the project logger — not `console.log` (see `web/FRONTEND_STYLE_GUIDE.md`).
- **API URLs:** build **`/api/${domainKey}/...`** or global paths as in `web/src/services/api/` — **never** `/api/v4/`.
- **Routing:** app uses **`/:domain/*`** with domain keys aligned to the backend registry.
- Reuse existing components and patterns in `web/src/components/` and `web/src/pages/` before adding new UI shells.
