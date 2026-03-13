# Archived interface (pre–Intelligence Dashboard rebuild)

This folder preserves the previous web UI for posterity (March 2026).

- **pages/** — All previous page components (Dashboard, Articles, Storylines, Intelligence Hub, Finance, etc.)
- **components/** — Previous Header, Footer, Navigation, DomainLayout, and all shared components
- **domains/** — Domain-specific components (e.g. Finance)

The live app now uses the new Intelligence Dashboard layout (hero status bar, Discover / Investigate / Monitor / Analyze nav, 3-column dashboard). API services, contexts, and utils remain in `src/services`, `src/contexts`, `src/utils` and are used by the new interface.

To reference or restore an old component, copy from this archive and fix imports (paths will need updating).
