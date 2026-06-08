# Public HTTPS demo (self-hosted)

**Purpose:** Run a **read-only** public beta: TLS, same-origin SPA + `/api`, production env hardening, and **server-enforced** demo mode so visitors cannot mutate data or enqueue jobs.

**Related:** [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) · [configs/env.example](../configs/env.example) · [DYNAMIC_DNS_WIDOW.md](DYNAMIC_DNS_WIDOW.md) · [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md) (nginx + API upstream + deploy SPA)

---

## 1. Hosting choice (operator decision)

Pick one pattern; the app does not require a specific provider.

| Option | When to use |
|--------|-------------|
| **Home + PopOS Caddy front door** (**current**) | Router **80/443 → PopOS**; Caddy routes `news-intelligence-ag.duckdns.org` → Widow nginx. See [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md). |
| **VPS / always-on host with public IP** | Stable `A`/`AAAA` DNS to that IP; simplest mental model. |
| **Cloudflare Tunnel (or similar)** | No inbound port forwarding; origin still uses TLS or terminates at Cloudflare. |

Use a **single public hostname** (e.g. `news.example.com`) for the UI and API (same origin).

---

## 2. TLS and reverse proxy

Serve the built SPA from disk and proxy `/api/` to FastAPI. Vite outputs to **`web/dist`** — point `root` / volume mount there.

### nginx (Widow LAN backend)

Widow nginx serves the SPA and proxies `/api/` to local uvicorn. **Public TLS** is on **PopOS Caddy** — see [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md).

- **`try_files`** for SPA: `$uri $uri/ /index.html`.
- **`location /api/`** → `proxy_pass` to `http://127.0.0.1:8000/api/`.
- Set `proxy_set_header Host $host;` and `X-Forwarded-Proto` so `NEWS_INTEL_TRUSTED_HOSTS` matches the public hostname.

See **[nginx/public-demo-site.conf.example](../nginx/public-demo-site.conf.example)** and **[nginx/widow-public-demo-site.conf.template](../nginx/widow-public-demo-site.conf.template)**.

### Caddy (PopOS WAN entry — production)

**Let's Encrypt** for `news-intelligence-ag.duckdns.org` is managed by **`ai-lab-caddy`** on PopOS. Config: **`HomeLab-AI-Stack/ai-lab/config/caddy/Caddyfile`**. See HomeLab [PUBLIC_HTTPS_ROUTING.md](../../HomeLab-AI-Stack/docs/PUBLIC_HTTPS_ROUTING.md).

### Bind API on localhost (recommended)

If the only client to port **8000** is the reverse proxy, bind Uvicorn to **`127.0.0.1:8000`** so **8000** is not exposed on the WAN. The plan’s firewall guidance assumes this pattern.

---

## 3. Firewall

- Allow **22** (SSH; optionally restrict source to your admin IP), **80**, **443**.
- **Do not** expose **5432** (PostgreSQL), **11434** (Ollama), or raw **8000** to the whole internet if the API is localhost-only behind the proxy.

---

## 4. Production API environment

Set at least:

| Variable | Notes |
|----------|--------|
| `NEWS_INTEL_ENV` | `production` |
| `NEWS_INTEL_CORS_ORIGINS` | `https://your-hostname` (same-origin SPA: one origin). |
| `NEWS_INTEL_TRUSTED_HOSTS` | Your public hostname (and `127.0.0.1,localhost` if health checks use them). |
| `NEWS_INTEL_ENABLE_API_DOCS` | Leave **unset** (docs off on the public process). |
| `NEWS_INTEL_SQL_EXPLORER` | Leave **unset** or `false`. |
| `LOG_LLM_FULL_TEXT` | **Off** if logs may leave the machine. |

See **§2** in [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) for the full table.

---

## 5. Read-only public demo (API)

Server middleware blocks **PUT**, **PATCH**, **DELETE**, and **POST** (except optional allowlist) when demo mode applies.

| Variable | Effect |
|----------|--------|
| `NEWS_INTEL_DEMO_READ_ONLY` | `true` / `1` — enable demo rules when Host matches (see below). |
| `NEWS_INTEL_DEMO_HOSTS` | Comma-separated hostnames **without port** (e.g. `demo.example.com`). Must match `Host` from the proxy. |
| `NEWS_INTEL_DEMO_READ_ONLY_ALL` | If `true` and `NEWS_INTEL_DEMO_HOSTS` is empty, apply read-only to **all** hosts (single-purpose demo server only). |
| `NEWS_INTEL_DEMO_POST_ALLOWLIST` | Optional comma-separated **path prefixes** allowing POST in demo (default: none). If **`NEWS_INTEL_PUBLIC_WEB_AUTH`** is on and demo read-only is on, include **`/api/public/auth/login`** and **`/api/public/auth/logout`** so admins can sign in. |

Implementation: `api/shared/middleware/demo_readonly.py`, registered in `api/main.py`.

**Discovery for the SPA:** `GET /api/public/demo_config` returns `{ success, data: { readonly, auth_enabled, role, authenticated, username, hint } }` so the UI can hide mutations and ops surfaces without a separate build flag.

---

## 5b. Guest vs admin session auth (optional)

When **`NEWS_INTEL_PUBLIC_WEB_AUTH=true`**, unauthenticated visitors default to **guest** (unless **`NEWS_INTEL_ALLOW_ANONYMOUS_GUEST=false`**). Guests cannot call **`/api/system_monitoring/*`**, **`/api/orchestrator/*`**, **`/api/user_management/*`**, or use mutating methods except **`POST /api/public/auth/login`** and **`POST /api/public/auth/logout`**. An **admin** session (JWT in an HTTP-only cookie after login) has full API access, still subject to demo read-only host rules.

| Variable | Effect |
|----------|--------|
| `NEWS_INTEL_PUBLIC_WEB_AUTH` | `true` / `1` — enable guest/admin RBAC + `/api/public/auth/*`. |
| `NEWS_INTEL_JWT_SECRET` | HS256 signing secret for the session cookie (falls back to **`JWT_SECRET`** if unset). Required when auth is on — the API refuses to start without it. |
| `NEWS_INTEL_ALLOW_ANONYMOUS_GUEST` | Default **true** — no login required for guest read UX. **false** forces login for API use (except auth bootstrap paths). |
| `NEWS_INTEL_AUTH_COOKIE_NAME` | Cookie name (default **`ni_session`**). |
| `NEWS_INTEL_AUTH_COOKIE_MAX_AGE_SECONDS` | Session lifetime (default **604800**). |
| `NEWS_INTEL_AUTH_COOKIE_SECURE` | Default **true** in production. |
| `NEWS_INTEL_AUTH_COOKIE_SAMESITE` | **`lax`** (default), **`strict`**, or **`none`**. |

**Database:** apply migration **`217`** (`api/scripts/run_migration_217.py`), then create users with **`api/scripts/seed_public_web_auth_users.py`** and **`NEWS_INTEL_BOOTSTRAP_ADMIN_PASSWORD`** (optional guest password env). Roles live in **`public.user_profiles.roles`** JSONB (`["admin"]` or `["guest"]`).

Implementation: `api/domains/public_auth/routes/auth.py`, `api/shared/middleware/public_web_auth.py`.

---

## 6. Frontend build

- **Same origin:** Omit **`VITE_API_URL`** so the browser calls `/api/...` on the same host.
- Output directory: **`web/dist`** (Vite default).
- Run **`npm ci`** then **`npm run build`** in `web/`. If **`tsc`** fails on your branch (type drift), use **`npm run build:bundle`** to run Vite only — output is still **`web/dist`**.
- Optional **demo UI at build time:** **`npm run build:demo`** (runs `tsc` + Vite) or **`npm run build:demo:bundle`** (Vite only, sets `VITE_PUBLIC_DEMO=true`).

Cosmetic UI hiding must **mirror** API rules; enforcement is always on the server.

---

## 7. Background workers

RSS, automation, and refinement **continue on the server**; the public site only **reads** stored articles and storylines. Demo mode does not require a second database if this process is demo-only.

---

## 8. Smoke test and kill switch

- From **outside LAN** (mobile data or another network): load `https://your-hostname`, confirm dashboard and a storyline load.
- Confirm a mutating action returns **403** with `demo_readonly` when demo env is active.
- **Kill switch:** point DNS away, stop the proxy, or firewall **443** — no schema migration required.

---

## 9. Proxy-level extras

HTTP Basic Auth, Cloudflare Access, or IP allowlists are optional **defense in depth** on top of in-app guest/admin auth (**§5b**) if abuse risk increases.
