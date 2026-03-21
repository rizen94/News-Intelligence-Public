# Security operations

**Purpose:** Practical hardening for **mixed** deployments (mostly LAN, sometimes reachable from the wider internet). This is **not** a penetration-test report or compliance checklist.

**Related:** [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) · [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md) · [MONITORING_SSH_SETUP.md](MONITORING_SSH_SETUP.md) · [DATABASE_CONNECTION_AUDIT.md](DATABASE_CONNECTION_AUDIT.md)

---

## 1. Threat model (short)

| Risk | Mitigation |
|------|------------|
| Anonymous access to API | Default: no JWT; rely on **network isolation** (firewall, VPN) or terminate TLS + auth at **reverse proxy**. Optional: shared secret on sensitive routes (future). |
| OpenAPI / `/docs` leaking surface | **Production** disables Swagger/ReDoc and `/openapi.json` unless `NEWS_INTEL_ENABLE_API_DOCS=true`. |
| Overly permissive CORS | **Production** uses explicit `NEWS_INTEL_CORS_ORIGINS` (comma-separated). Empty = no browser CORS origins. |
| Host header attacks | **Production** uses `NEWS_INTEL_TRUSTED_HOSTS`; if unset, defaults to `localhost` and `127.0.0.1` only — **set your LAN hostname or IP** if browsers hit the API by IP. |
| Error bodies leaking internals | **Production** returns generic 500 payloads; details stay in server logs. |
| Brute force / scraping | **Production** enables in-app `SecurityMiddleware` (rate limit + security headers). Prefer **edge** rate limits (nginx, cloud WAF) when exposed. |
| Secrets in Git | `.env`, `api/config/.secrets`, passwords files — see §4. |
| Untrusted content | RSS/HTML/PDF and LLM outputs — see §5. |

---

## 2. Environment variables (`api/main.py` + `config/settings.py`)

| Variable | Values | Effect |
|----------|--------|--------|
| `NEWS_INTEL_ENV` | `development` (default) or `production` | Production tightens CORS, hosts, OpenAPI, errors, and enables security middleware. |
| `NEWS_INTEL_CORS_ORIGINS` | Comma URLs, e.g. `http://localhost:3000,https://app.example.com` | **Required** for browser SPAs on another origin in production. |
| `NEWS_INTEL_TRUSTED_HOSTS` | Comma hostnames/IPs matching `Host` header | **Set** for LAN access by IP or hostname (e.g. `192.168.93.99,myserver`). |
| `NEWS_INTEL_ENABLE_API_DOCS` | `true` / `1` | Re-enable `/docs`, `/redoc`, `/openapi.json` in production (avoid on the public internet). |
| `NEWS_INTEL_SECURITY_MIDDLEWARE` | `true` / `1` | Force security middleware in **development** (optional). |
| `NEWS_INTEL_RATE_LIMIT_PER_MINUTE` | Integer (default `120`) | Per-IP in-process limit when middleware is on. |
| `NEWS_INTEL_SQL_EXPLORER` | `true` | Read-only SQL explorer in Monitor — **high impact**; anyone who can reach the API can read the DB. Keep off outside trusted networks. |
| `LOG_LLM_FULL_TEXT` | `true` | Logs full prompts/responses — may contain PII or article text; keep **off** in shared log sinks. |
| `CRON_HEARTBEAT_KEY` | Long random string | **Optional.** When set, `POST /api/system_monitoring/cron_heartbeat` with header **`X-Cron-Heartbeat-Key`** matching this value can append a row to **`automation_run_history`** (e.g. phase `cron_rss`) so cron runs are visible without log files. If unset, the endpoint returns **501** (not configured). Treat like any shared secret; restrict network access to the API. |

Copy examples into project-root `.env` from [configs/env.example](../configs/env.example).

---

## 3. Network and TLS

- **LAN-only:** Bind API to an internal interface; firewall **WAN** → API ports (8000) unless you intend exposure.
- **Internet-facing:** Put **nginx** (or similar) in front: TLS termination, `proxy_set_header Host`, optional client certificates or basic auth at the edge. Align `NEWS_INTEL_TRUSTED_HOSTS` with the hostname clients send.
- **PostgreSQL / Ollama:** Do not expose `5432` or `11434` to the internet without tunneling or auth.
- **SSH:** Prefer keys over passwords for automation hosts (see [MONITORING_SSH_SETUP.md](MONITORING_SSH_SETUP.md)).

---

## 4. Secrets and supply chain

- **Never commit** `.env`, `.db_password_widow`, or API keys. Root `.gitignore` already excludes common patterns; add new secret filenames to `.gitignore` if you introduce them.
- **Rotate** DB passwords and API keys if a laptop or repo clone leaks.
- **Dependency audit:** Periodically run `uv sync` / review `uv.lock`; consider `pip-audit` on the resolved environment for CVEs.
- **Historical code** may still mention old default passwords in comments or archived docs — treat as **documentation only**, not runtime config ([DATABASE_CONNECTION_AUDIT.md](DATABASE_CONNECTION_AUDIT.md)).

---

## 5. Untrusted input (data plane)

- **RSS and HTML:** Treat as untrusted. Avoid executing embedded scripts in admin UIs; sanitize if rendering HTML previews.
- **PDFs / documents:** Parsing can be abused with malicious files — run collectors with least privilege; quarantine unusual uploads if you add user uploads.
- **LLM prompt injection:** Article text can instruct the model to ignore policies. Use structured extraction where possible; do not place secrets inside prompts; cap prompt size and log without echoing credentials.
- **SSRF:** If you add endpoints that fetch arbitrary URLs, restrict schemes (https only), block RFC1918/metadata IPs, or require allowlists.

---

## 6. Operational checklist (when exposing the API)

1. Set `NEWS_INTEL_ENV=production`.
2. Set `NEWS_INTEL_CORS_ORIGINS` to real UI origins.
3. Set `NEWS_INTEL_TRUSTED_HOSTS` to every hostname/IP the browser or proxy uses in `Host`.
4. Leave `NEWS_INTEL_ENABLE_API_DOCS` unset (docs off) unless you need them internally.
5. Ensure TLS at the reverse proxy; enable HSTS there (in-app middleware also sets HSTS when middleware runs).
6. Confirm `NEWS_INTEL_SQL_EXPLORER` and `LOG_LLM_FULL_TEXT` are off unless you accept the risk.
7. Firewall DB, Redis, and Ollama from untrusted networks.

---

## 7. JWT / future auth

OpenAPI text may mention future JWT. Until implemented, **do not assume** bearer auth protects routes — protection is **network + env profile + edge proxy**.
