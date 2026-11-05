# Frontend debugging — quick reference

Quick-reference card for debugging the React SPA (v2 shell, product-root routing). Covers **dev setup**, **API connection flow**, **common failure modes**, and **browser-level diagnostics**. All paths relative to `/home/pete/Documents/projects/News Intelligence/web/src/`.

---

## Architecture at a glance

| Layer | What it does |
|-------|-------------|
| **v2 shell** (`web/src/v2/`) — News, Admin pages; product root via `ProductRootSwitcher` (`/`, `/finance`, `/admin`). Legacy `/v2/*` routes all redirect. |
| **Finance** (`web/src/finance/`) — independent route tree under `/finance/*`. |
| **API routing** (`apiService.ts`) — Proxy over domain modules (`articlesApi`, `storylinesApi`, etc.). No direct fetch calls from components. |
| **Connection manager** (`apiConnectionManager.ts`) — Single axios instance with request interceptor that mutates `baseURL` per route type (domain-prefixed vs global prefix). |
| **Error handling** (`errorHandler.ts`) — Global `window:error`, `unhandledrejection` listeners + HTTP error classification. Routes to `loggingService`. |

---

## Dev environment setup

### Start React dev server

```bash
cd /home/pete/Documents/projects/News Intelligence/web
npm start          # Vite on :3000, proxies /api → http://localhost:8000
# or
./start-dev.sh     # Same + HTML fallback on :3001 (deprecated)
```

### Start the full stack (API + frontend)

| Host | What runs where | Port |
|------|----------------|------|
| **Widow** (production API host) | `news-intelligence-api-public.service` (uvicorn, PID manages itself via systemd) | :8000 API |
| **Widow** (dev local) | Manual `uvicorn api.main:app --reload --port 8000` | :8000 |
| **Widow → PopOS** | Vite dev on PopOS :3000, `/api` proxied to Widow `192.168.93.101:8000` via vite.config.mts or env var | :3000 + :8000 tunnel |

### Proxy configuration

**vite.config.mts** hard-codes `/api → http://localhost:8000`. For remote API (cross-host dev), override:

```bash
# .env file in web/ root, or:
VITE_API_URL=http://192.168.93.101:8000
```

This skips the Vite proxy entirely and sends requests directly to the backend. **Important:** CORS must be allowed on the API host for this to work (check `api/main.py` CORS middleware).

### Build / production

```bash
./build-react.sh    # Builds to web/dist/ — served by nginx or Caddy
```

Production public site: **https://news-intelligence-ag.duckdns.org** (PopOS Caddy → Widow nginx). Zero VITE_API_URL needed — all `/api/*` requests are same-origin via nginx reverse-proxy.

---

## Product root switcher (broadband vs finance vs admin)

Routes determine which API path prefix is used:

| Root | Routes matched by `detectProductRoot()` | API path style |
|------|------------------------------------------|---------------|
| **News** `/` | `/`, `/news/*`, `/current/*`, `/research/*`, `/one-offs/*`, `/storylines/*`, `/entities/*`, `/v2/*` | `/api/{domain}/...` or global prefix |
| **Finance** `/finance` | `/finance/trackers`, `/finance/markets`, `/finance/reporting` | Finance-specific API routes |
| **Admin** `/admin` | `/admin` (Monitor, Work, SQL, Audit) | `GET /api/system_monitoring/*` etc. — global prefix only |

**Switcher component:** `web/src/shell/ProductRootSwitcher.tsx`. Links to the three roots: News (`NEWS_HOME`), Finance (`FINANCE_HOME`), Admin (`ADMIN_HOME`). Uses `paths.ts` constants.

**Common gotcha:** After changing product root, old pages may cache stale domain context. Hard-refresh or clear `localStorage.news_intelligence_api_url` if API calls start routing incorrectly.

---

## API connection flow (critical path)

When a component makes any API call, here's what happens:

```
Component → apiService.ts → Proxy → getApi() → apiConnectionManager → axios instance → request interceptor → baseURL mutation → dispatch
```

### 1. Connection initialization

- **Lazy:** `apiService.ts` uses a Proxy; `getApi()` instantiates once on first call.
- **Singleton:** Single axios instance per page load. No re-initialization.

### 2. Request interceptor (the most common debugging pain point)

The interceptor mutates `config.baseURL` based on the first path segment after `/api/`:

```typescript
const globalApiPrefixes = [
  'system_monitoring', 'watchlist', 'intelligence', 'public',
  'reader', 'editorial', 'pulse', 'articles', 'storylines', ...
];
```

| Segment in `/api/{X}/...` | Behavior |
|--------------------------|----------|
| **In `globalApiPrefixes`** (e.g. `system_monitoring`, `intelligence`) | Uses `getApiOrigin()` — strips any path prefix so URL stays `/api/system_monitoring/...` (no double-prefix) |
| **Domain key** (`politics`, `finance`, `science-tech`) or registry domain | Appends `{currentDomain}` to the path: `/api/politics/storylines/...` |
| **Neither** (unknown segment) | Falls through — no prefix added, may 404 at backend |

### 3. Base URL resolution order

```
1. import.meta.env.VITE_API_URL      ← Vite env var (highest priority)
2. localStorage.news_intelligence_api_url   ← persisted user setting
3. '' (empty string)                 ← default — relative URL, relies on Vite proxy or same-origin
```

**Debugging tip:** Open browser DevTools → Application → Local Storage → `news_intelligence_api_url`. If this has a stale value from a previous dev run, it will override the Vite proxy and cause connection failures.

### 4. Axios interceptors

- **Request interceptor:** Mutates baseURL (see above), no body transformation.
- **Response interceptor:** On error, delegates to `errorHandler.handleNetworkError()` or `handleApiError()`. Returns `Promise.reject(error)` — always propagates up to component.

---

## Common failure modes and fixes

### 1. All API calls return 404 with domain-prefixed paths (e.g. `/api/politics/...`)

**Cause:** The request interceptor sees a non-global segment and injects `getCurrentDomain()`. If `localStorage.news_intelligence_api_url` has an absolute URL, the path becomes `{url}/api/politics/...`.

**Fix:** Clear `localStorage.news_intelligence_api_url`, reload. In dev, ensure VITE_API_URL is not set (let proxy handle it).

### 2. API calls hang / timeout (no error shown in UI)

**Cause:** Axios timeout (`API_CONFIG.timeout` defaults to `VITE_API_TIMEOUT` env var, normally 30s). Long-running endpoints like `processing_progress` have internal 300s polling but axios may kill first.

**Fix:** Check `apiConfig.ts` — if `VITE_API_TIMEOUT` is set too low, increase it. For polling endpoints, the UI should check response status before re-polling.

### 3. Cross-origin (CORS) errors on cross-host dev

**Cause:** `VITE_API_URL=http://192.168.93.101:8000` but the API server's CORS middleware only allows `localhost` or specific origins.

**Fix:** On Widow, check `api/main.py` for CORS settings. Add PopOS dev host origin to allowed list if needed.

### 4. Product root not switching (clicking Admin/Finance stays on News)

**Cause:** `ProductRootSwitcher.tsx` uses `useLocation()`. If the router isn't mounted or hash mode is used, path detection fails. Also: old pages at `/v2/*` redirect to `/` — check browser history.

**Fix:** Navigate directly: `http://localhost:3000/admin`, `http://localhost:3000/finance`. Check DevTools Console for React router errors.

### 5. Monitor page shows "no data" or stale metrics

**Cause:** Monitor polls `/api/system_monitoring/*` endpoints. If the API is unreachable, it shows cached/stale state. The `APIConnectionStatus` component should show a red dot — if not, the health check itself may be failing.

**Fix:** Check browser DevTools → Network tab for `/api/system_monitoring/health`. Verify `NI_PROMETHEUS_METRICS_ENABLED=true` (if Grafana data is expected). Monitor SPA polls overview every ~15s and pulse similarly.

### 6. Page hangs on first load after rebuild

**Cause:** Vite HMR or module caching issue. The lazy-loaded Proxy in `apiService.ts` may hold a stale reference across hot-reloads.

**Fix:** Hard refresh (Ctrl+Shift+R). In dev, if it persists, restart the Vite dev server (`npm start`).

### 7. Vite build fails with TypeScript errors

**Cause:** Type errors in production build mode only (dev allows more lenient checking). Check for:
- Missing type imports from `@types/*` packages
- Mismatched API response types (check `web/src/types/api.ts`)
- Unhandled promise rejections without catch

**Fix:** Run `npx tsc --noEmit` to find type errors before building. Then `./build-react.sh`.

### 8. Grafana deep link broken in Monitor UI

**Cause:** The deep link uses `VITE_NEWS_INTEL_GRAFANA_URL` (or `localStorage.news_intel_grafana_url`). If set incorrectly or missing, the "Open Grafana" button navigates to a blank URL.

**Fix:** Check Env vars or browser localStorage for `news_intel_grafana_url`. Also verify `api/monitoring/grafana/ni-ops-dashboard.json` exists on the Homelab host (PopOS), not Widow.



---

## Live debugging shortcuts (agent shorthand)

### Interceptor routing — what to check where

In `web/src/services/apiConnectionManager.ts`:
```ts
// Check current domain context:
import { getCurrentDomain, ProductRoot } from '../utils/domainHelper';
console.log('root:', localStorage.getItem('product_root')); // 'news'|'finance'|'admin'
console.log('domain:', getCurrentDomain());

// At interceptor site — log what's happening:
config.url // full path after baseURL
config.baseURL // the origin after mutation
```

Quick check — is domain key being appended correctly?
```ts
// Paste in browser console:
const prefixes = ['system_monitoring','watchlist','intelligence','public','reader','editorial','pulse'];
const testPath = '/api/politics/storylines/123';
const seg = testPath.split('/')[3];
console.log('seg:', seg);
console.log('isGlobal:', prefixes.includes(seg));
// true → gets getApiOrigin() (strips path)
// false → treated as domain key (appended to path)
```

**Beware:** `politics`, `finance` (as domain key, not product root), `science-tech` are NOT in global prefix list. `/api/finance/storylines/...` will append currentDomain again if interceptor sees `finance` segment — double-prefix bug. Verify against actual domain registry order.

### Backend symptom → frontend failure map

| Frontend symptom | Likely backend cause | Where to check |
|------------------|---------------------|----------------|
| All requests timeout (30s) | API process down / systemd not running | `systemctl status news-intelligence-api-public.service` on Widow |
| Some return 504 Gateway Timeout | **Caddy default upstream timeout (30s)** — *fixed* with `timeout upstream 120s` at Caddyfile:~30. For `/storylines/{id}` pack load: timeline source enrichment (~50 event-by-event DB lookups) and entity dossier fetches (~15 per entity) — *both fixed* with bulk `WHERE id = ANY(%s::int[])` queries in `timeline_builder_service.py` and `storyline_pack.py`. | PopOS Caddy config (`HomeLab-AI-Stack/ai-lab/config/caddy/Caddyfile:~30`); Widow nginx `proxy_read_timeout`; verify Caddy reload after changes |
| Intermittent connection refused | API process crashed / out of memory | `journalctl -u news-intelligence-api-public.service -n 20` |
| Pool exhaustion errors in response body | PgBouncer pools full | Check PgBouncer pool usage on Widow; `db_pool_pressure_advisory` table |
| "Circuit breaker open" message | Ollama CB triggered (embeddings) | `GET /api/system_monitoring/circuit_breakers`; `POST .../reset` to clear |
| CORS error only in cross-host dev | CORS middleware not allowing PopOS origin | `api/main.py` → `CORSMiddleware` allowed_origins list |
| 404 on known route | Wrong product root context | Check `getCurrentDomain()` value; localStorage `product_root` key |
| Stale data in Monitor | API returning cached response / stale PgBouncer conn | Force-refresh Monitor (Ctrl+Shift+R); check `system_monitoring/health` endpoint |
| Finance routes work, news doesn't | Domain-specific route not registered | Check `/api/{domain}/...` registry; YAML domains config |

### Backend verification commands (run on Widow)

```bash
# API running?
systemctl is-active news-intelligence-api-public.service

# Ollama circuit breaker state
curl -s http://localhost:8000/api/system_monitoring/circuit_breakers | jq .

# DB pool pressure
psql -U newsapp -d news_intel -c "SELECT * FROM public.db_pool_pressure_advisory LIMIT 1;"

# Ollama health (PopOS)
curl -s http://127.0.0.1:11435/api/health | jq .

# Check if automation manager is running
pgrep -f AutomationManager
```

### Finance vs Admin API path distinction

| Feature area | Frontend route | Backend path prefix | Notes |
|-------------|---------------|---------------------|-------|
| Finance trackers/markets | `/finance/trackers`, `/finance/markets` | Not `/api/finance/*` — uses `apiService.financeTracker` etc. (separate service layer) | Finance has its own API client module, NOT through domain interceptor |
| Admin Monitor | `/admin` | `GET /api/system_monitoring/...` | Global prefix only; no domain key ever applied |
| Admin SQL/Audit | `/admin/sql`, `/admin/audit` | `GET /api/system_monitoring/query`, etc. | Same global namespace as Monitor |
| Public demo | Public route | `GET /api/public/demo_config` | Available on duckdns.org without auth |

**Key point:** Finance is NOT routed through the domain interceptor in `apiConnectionManager.ts`. It uses its own API client (`web/src/services/financeApi.ts` or similar). If Finance APIs fail, check there — not the connection manager.

### Fast test: isolate frontend from backend

1. Open browser DevTools → Network tab
2. Filter by `/api/`
3. Click a component that should load data
4. Look at the request URL shown:
   - Correct for domain API: `http://localhost:3000/api/politics/storylines?limit=5`
   - Stuck with localStorage override: `http://192.168.93.101:8000/api/politics/storylines?limit=5` (cross-host)
   - Double-prefix bug: `http://localhost:8000/api/finance/politics/storylines?limit=5`

### Clear cache chain (if nothing else works)

```ts
// Paste in browser console — full frontend reset:
localStorage.clear();
location.reload();
```

Or selectively:
```ts
localStorage.removeItem('news_intelligence_api_url');  // clears API URL override
localStorage.removeItem('product_root');                // resets product root to default
location.reload();
```

### Vite proxy bypass (force direct API call in dev)

```bash
# web/.env — sets VITE_API_URL, skips Vite proxy entirely
VITE_API_URL=http://192.168.93.101:8000
```

After setting, **restart vite dev server** for it to take effect (env vars loaded at startup).

### Prod path resolution (duckdns.org)

Production has NO VITE_API_URL set. All `/api/*` requests are same-origin via nginx reverse-proxy → PopOS Caddy → Widow API:
```
browser → duckdns.org → PopOS Caddy (TLS) → Widow nginx (:443) → localhost:8000/api/...
```

If prod APIs fail but dev works, check:
1. Nginx config on Widow (`/etc/nginx/sites-enabled/`)
2. Caddyfile on PopOS — is it proxying `/api` to Widow?
3. DNS — does `news-intelligence-ag.duckdns.org` still point to PopOS Caddy?
---

## Browser diagnostics checklist

### Console tab
1. **Red errors:** Any unhandled errors appear here via `errorHandler.ts`'s global listeners + `loggingService`.
2. **Axios errors:** `Network Error` = connection failed; `404` = route mismatch (check interceptor); `500` = backend error (see API logs on Widow).
3. **React warnings:** Check for deprecations, missing keys, or prop type issues — these can cause silent rendering bugs.

### Network tab
1. **Filter by `/api/`**: See all requests, their URLs, status codes, and timing.
2. **Check the first segment after `/api/`:** Confirms interceptor is routing correctly.
3. **Verify `baseURL` in request headers:** The full URL shown should match what you expect for the product root.
4. **Look for stalled requests:** Indicates backend slow response, pool exhaustion, or circuit breaker state (`defer` = pending, not timeout).

### Application tab → Local Storage
| Key | Purpose |
|-----|---------|
| `news_intelligence_api_url` | User-set API base URL (overrides VITE_API_URL if present) |
| `news_intel_grafana_url` | Grafana deep link base URL |

### Application tab → Service Workers
1. **Check for stale cache entries** from old builds. Click "Unregister" if the app is serving cached pages.
2. **Check IndexedDB** — if any components use it (e.g. storyline caches).

### React DevTools
1. **Component tree:** Find which component is rendering incorrectly. Look for unexpected sub-trees or empty containers.
2. **Props panel:** Check `useLocation()`, `useParams()` values in route-aware components.
3. **Profiler:** Record a render to see if re-renders are triggered by high-frequency polling (Monitor's 15s interval).

---

## Vite dev server HMR tips

- **Port conflicts:** If :3000 is taken, Vite tries :3001, then :3002. Check terminal output for the actual port.
- **Native watching:** `vite.config.mts` uses native file watching (`usePolling: false`) — faster than polling on Linux.
- **Sourcemaps:** Built with `sourcemap: true`. Source maps appear in DevTools → Sources tab under original source files.
- **Manual chunks** (prod only): `vendor`, `mui`, `recharts`, `d3` are split in `rollupOptions.output.manualChunks`.

---

## Quick restart / reset sequence

When frontend is in an unrecoverable state:

```bash
# 1. Kill any running processes
pkill -f "vite\|node.*3000\|start-frontend"

# 2. Clear stale state
cd /home/pete/Documents/projects/News Intelligence/web/src
# Clear localStorage via DevTools (Application → Local Storage → right-click → Clear All)

# 3. Clean and restart
npm run clean  # if exists, or: rm -rf node_modules/.vite

cd /home/pete/Documents/projects/News Intelligence/web
npm start      # Vite on :3000 + proxy to :8000
```

---

## File map for quick navigation

| Concern | File(s) |
|---------|---------|
| API service layer | `web/src/services/apiService.ts` (Proxy + domain delegation) |
| API connection manager | `web/src/services/apiConnectionManager.ts` (axios instance + interceptors) |
| Error handling | `web/src/services/errorHandler.ts` (global listeners) |
| Logging | `web/src/services/loggingService.ts` |
| Config / routing URLs | `web/src/config/apiConfig.ts`, `web/src/config/grafanaConfig.ts` |
| Product root switcher | `web/src/shell/ProductRootSwitcher.tsx` |
| Route definitions | `web/src/paths.ts` (NEWS_HOME, FINANCE_HOME, ADMIN_HOME) |
| Vite config | `web/vite.config.mts` |
| Types | `web/src/types/api.ts` |
| Domain helpers | `web/src/utils/domainHelper.ts` |
| Reader-specific API | `web/src/v2/services/readerApi.ts` |
| Components | `web/src/components/` (e.g. `APIConnectionStatus/`) |
