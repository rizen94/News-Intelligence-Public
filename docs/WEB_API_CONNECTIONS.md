# Web frontend — API connections

How the React app talks to the API and what to do when data doesn't load.

---

## URL scheme (March 2026)

All frontend API URLs use **`/api/...`** (no version prefix). This matches the backend
route structure, where every router mounts at `/api`.

| Route type | Frontend URL example | Backend route |
|------------|---------------------|---------------|
| Domain-scoped | `/api/politics/articles` | `/api/{domain}/articles` |
| Domain-scoped (finance) | `/api/finance/finance/gold/history` | `/api/{domain}/finance/gold/history` |
| Global (system) | `/api/system_monitoring/health` | `/api/system_monitoring/health` |
| Active domains (SPA) | `/api/system_monitoring/registry_domains` | `/api/system_monitoring/registry_domains` |
| Global (orchestrator) | `/api/orchestrator/dashboard` | `/api/orchestrator/dashboard` |
| Context-centric | `/api/entity_profiles`, `/api/contexts` | `/api/entity_profiles`, `/api/contexts` |
| Watchlist | `/api/watchlist` | `/api/watchlist` |

> **History:** Frontend URLs previously used `/api/...` but the backend never
> had a `/v4/` prefix in its routes. This mismatch was corrected by removing `/v4/`
> from all frontend API service files and from the request interceptor in
> `apiConnectionManager.ts`.

---

## How it works

1. **Base URL**
   - From `VITE_API_URL` (build time) or `localStorage` key `news_intelligence_api_url` (in-app settings).
   - If neither is set, base URL is **empty** (`''`).

2. **Default (empty base)**
   - All requests are **relative** (e.g. `/api/politics/articles`, `/api/context_centric/status`).
   - The browser sends them to the **same origin** as the page (e.g. `http://localhost:3000`).
   - **In development**, Vite proxies `/api` to `http://localhost:8000`.
   - So the **API must be running on port 8000** or the proxy fails and you get no data.

3. **Request interceptor**
   - Located in `apiConnectionManager.ts`.
   - Treats a first path segment as **domain-scoped** when it matches an active key from [`domainHelper`](../web/src/utils/domainHelper.ts) (loaded from **`/api/system_monitoring/registry_domains`**, with a static fallback list).
   - Detects whether a URL is a **global route** (system_monitoring, orchestrator, watchlist, context_centric, entity_profiles, etc.) or a **domain-scoped route**.
   - **Global routes:** base URL is set to origin only (prevents double-prefixing if a custom URL has a path).
   - **Domain-scoped routes:** if the URL does not already contain the current domain, the interceptor injects it (e.g. `/api/topics/merge` becomes `/api/politics/topics/merge`).
   - Most API service files already include the domain in their URLs. The interceptor is a safety net for the few that don't.

4. **Custom API URL**
   - If base is set (e.g. `http://192.168.1.10:8000`):
     - Domain-prefixed routes use that full base.
     - Global routes use **origin only** (no path) so the path stays `/api/...`.

5. **Connection check**
   - The hero bar shows **Connected** / **Disconnected** (and retry).
   - Health check hits `/api/system_monitoring/health` using the same base/origin logic as above.

---

## When data is "lost" or doesn't load

- **Disconnected** in the bar → API not reachable.
  - **Dev (Vite on 3000):** Start the API on port 8000, e.g.
    `cd api && python3 -m uvicorn main:app --host 0.0.0.0 --port 8000`
  - **Custom URL:** Ensure that host/port is correct and the API is running there.
- **Connected but empty lists** → API is up; data may be empty (e.g. no finance feeds) or a specific endpoint may be failing. Check Network tab and API logs.
- **`ECONNREFUSED` in Vite terminal** → API server is not running on port 8000. Start it.

---

## Files involved

| File | Role |
|------|------|
| `web/src/config/apiConfig.ts` | `getCurrentApiUrl()`, `getApiOrigin()`; comments describe the flow. |
| `web/src/services/apiConnectionManager.ts` | Single axios instance; request interceptor classifies routes (global vs domain-scoped) and sets base URL accordingly; `testConnection()` uses same URL rules. |
| `web/src/services/api/client.ts` | `getApi()` returns the shared axios instance. |
| `web/src/services/api/*.ts` | Per-domain API modules. Most build URLs with the domain already included (e.g. `/api/${domainKey}/articles`). |
| `web/vite.config.mts` | Dev proxy: `/api` → `http://localhost:8000`. No rewrite — path is forwarded as-is. |
| `web/src/components/APIConnectionStatus/APIConnectionStatus.tsx` | Shows Connected/Disconnected and retry; tooltip hints at port 8000 when disconnected. |
| `web/src/layout/HeroStatusBar.tsx` | Renders APIConnectionStatus so it's visible on every page. |

---

## Quick checklist

- [ ] API process is running (e.g. uvicorn on port 8000).
- [ ] In dev, frontend is served from the Vite dev server (e.g. port 3000) so the proxy is active.
- [ ] If you set a custom API URL, it is reachable from the browser and the path (if any) matches how the backend is mounted.
- [ ] Hero bar shows **Connected**; if it shows **Disconnected**, click retry after starting the API.
