# Archived SPA modules

Outside `web/tsconfig.json`'s `include` (`src/**/*`), so nothing here is typechecked, linted,
or bundled. Do not import from `src/`.

## v12 cutover

Unused after cutover redirects.

- Briefings / ReportPage → `/editor`
- StorylineDiscovery → episode list

## 2026-09 waste review

No import, lazy import, or route reference from `src/` when archived.

| Module | Note |
|--------|------|
| `components/Monitoring/RealtimeMonitor.tsx` | Superseded by `pages/Monitor/MonitorPage.tsx` |
| `components/Analytics/SystemAnalytics.tsx` | Superseded by Monitor dimension metrics |
| `components/Editorial/AddToPackageButton.tsx` | Package attach now runs from the Editorial modal pages |
| `components/citations/CitationDrawer.tsx` | Citations render inline in `NewsStoryReader` |
| `components/Footer/Footer.tsx` + `.css` | `MainLayout` has no footer slot |
| `components/shared/DomainIndicator`, `DomainBreadcrumb`, `DomainRouteGuard`, `LegacyRedirect` | Domain routing collapsed into `App.tsx` `/:domain` + `MainLayout` |
| `domains/Finance/MarketResearch`, `MarketPatterns`, `CorporateAnnouncements` | Pre-`/:domain` finance pages; the live finance surfaces are under `pages/` |
| `services/frontendHealthService.ts` | Superseded by `apiConnectionManager.ts` |
| `utils/safeServiceCall.ts` | Superseded by `ErrorBoundary` + per-call handling in `services/api/` |
