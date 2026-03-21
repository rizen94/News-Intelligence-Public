# Public HTTPS demo (self-hosted)

**Purpose:** Run a **read-only** public beta: TLS, same-origin SPA + `/api`, production env hardening, and **server-enforced** demo mode so visitors cannot mutate data or enqueue jobs.

**Related:** [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) · [configs/env.example](../configs/env.example) · [DYNAMIC_DNS_WIDOW.md](DYNAMIC_DNS_WIDOW.md) · [WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md) (nginx + API upstream + deploy SPA)

---

## 1. Hosting choice (operator decision)

Pick one pattern; the app does not require a specific provider.

| Option | When to use |
|--------|-------------|
| **VPS / always-on host with public IP** | Stable `A`/`AAAA` DNS to that IP; simplest mental model. |
| **Home + dynamic DNS** | **Router** = main entry (WAN **80/443** → LAN proxy host). DDNS on the **router** if supported; else **[DYNAMIC_DNS_WIDOW.md](DYNAMIC_DNS_WIDOW.md)** fallback script on Widow. Do not expose DB/Ollama. |
| **Cloudflare Tunnel (or similar)** | No inbound port forwarding; origin still uses TLS or terminates at Cloudflare. |

Use a **single public hostname** (e.g. `news.example.com`) for the UI and API (same origin).

---

## 2. TLS and reverse proxy

Serve the built SPA from disk and proxy `/api/` to FastAPI. Vite outputs to **`web/dist`** — point `root` / volume mount there.

### nginx

- Terminate TLS (e.g. **certbot** with the nginx plugin, or manual certs).
- **HTTP → HTTPS** redirect on port 80.
- **`try_files`** for SPA: `$uri $uri/ /index.html`.
- **`location /api/`** → `proxy_pass` to the API (e.g. `http://127.0.0.1:8000/api/`).
- Set `proxy_set_header Host $host;` and `X-Forwarded-Proto` so `NEWS_INTEL_TRUSTED_HOSTS` matches the public hostname.

See **[nginx/public-demo-site.conf.example](../nginx/public-demo-site.conf.example)** for a starting server block.

### Caddy

Automatic Let’s Encrypt is typical. See **[Caddyfile.example](../Caddyfile.example)** at the repo root.

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
| `NEWS_INTEL_DEMO_POST_ALLOWLIST` | Optional comma-separated **path prefixes** allowing POST in demo (default: none). Prefer empty for public beta. |

Implementation: `api/shared/middleware/demo_readonly.py`, registered in `api/main.py`.

**Discovery for the SPA:** `GET /api/public/demo_config` returns `{ success, data: { readonly, hint } }` so the UI can hide mutations without a separate build flag.

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

## 9. Optional edge auth (not v1)

HTTP Basic Auth, Cloudflare Access, or IP allowlists are **out of scope** for the first public beta; add at the reverse proxy if abuse risk increases.
