# Widow + public HTTPS (PopOS Caddy → Widow nginx)

**Current production pattern (June 2026):** Both public hostnames share one **WAN IP** (`73.167.39.74`). **PopOS Caddy** (`ai-lab-caddy`) is the **only** WAN entry on **:80/:443**. It terminates **Let's Encrypt** TLS and routes by hostname:

| Public hostname | Caddy upstream | Serves |
|-----------------|----------------|--------|
| `legion-agent.duckdns.org` | `http://ai-lab-openwebui:8080` | HomeLab **Open WebUI** |
| `news-intelligence-ag.duckdns.org` | `https://192.168.93.101` (Widow LAN) | **News Intelligence** SPA + `/api` |

**Do not** port-forward WAN **:443** to both PopOS and Widow — only PopOS receives public HTTPS. Widow nginx is a **LAN backend** behind Caddy.

---

## Request flow (News Intelligence)

```
Browser → DNS (DuckDNS) → WAN :443 → PopOS ai-lab-caddy
  → TLS (Let's Encrypt, Caddy-managed)
  → reverse_proxy https://192.168.93.101  (tls_insecure_skip_verify — Widow uses internal self-signed cert)
    → Widow nginx :443
      → /           → /var/www/news-intelligence/web/dist  (React SPA)
      → /api/       → http://127.0.0.1:8000/api/  (uvicorn on Widow)
```

**Verified:** `https://news-intelligence-ag.duckdns.org/` and `/api/system_monitoring/health` return **200 / healthy** through this path.

---

## Where components run

| Component | Host | Notes |
|-----------|------|-------|
| **Public TLS** | PopOS Caddy | Config: `HomeLab-AI-Stack/ai-lab/config/caddy/Caddyfile` |
| **SPA + nginx `/api` proxy** | Widow | `/etc/nginx/sites-available/news-intelligence-public` |
| **FastAPI (AutomationManager)** | Widow | `/opt/news-intelligence` — `:8000` |
| **PostgreSQL `news_intel`** | Widow | `:5432` LAN-only |
| **Local Ollama (8B-class)** | Widow | GTX 1080 8 GB — see [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) |
| **70B narrative finisher** | PopOS `.99` | RTX 5090 — `OLLAMA_POP_OS_HOST=http://192.168.93.99:11434` |

---

## Router / DNS

| Setting | Value |
|---------|-------|
| **DDNS** | DuckDNS on router or single updater (not both router + Widow cron) |
| **Port forward WAN 80** | → **PopOS** LAN IP (`192.168.93.99`) |
| **Port forward WAN 443** | → **PopOS** LAN IP (`192.168.93.99`) |
| **Do not forward** | 5432, 11434, 8000 to WAN |

Both DuckDNS names (`legion-agent`, `news-intelligence-ag`) point at the **same WAN IP**; Caddy distinguishes them by **SNI / Host**.

---

## Widow nginx (LAN backend)

Widow nginx still serves the SPA and proxies `/api/` to local uvicorn. Public visitors never hit Widow's certificate — Caddy presents the Let's Encrypt cert.

```bash
# On Widow — upstream must be localhost (API on same host)
grep upstream /etc/nginx/sites-available/news-intelligence-public
# expect: server 127.0.0.1:8000;

# Deploy SPA build
./scripts/deploy_public_demo_to_widow.sh
```

**certbot on Widow is optional** when Caddy terminates public TLS. Widow may keep a self-signed cert for the PopOS→Widow hop (Caddy uses `tls_insecure_skip_verify`).

---

## PopOS Caddy config (authoritative)

File: **`HomeLab-AI-Stack/ai-lab/config/caddy/Caddyfile`**

After edits:

```bash
cd ~/Documents/projects/HomeLab-AI-Stack
docker exec ai-lab-caddy caddy validate --config /etc/caddy/Caddyfile
docker exec ai-lab-caddy caddy reload --config /etc/caddy/Caddyfile
```

Caddy obtains/renews Let's Encrypt certificates automatically for each hostname block.

---

## API env on Widow (public hostname)

In `/opt/news-intelligence/.env` (or `configs/.env`):

```bash
NEWS_INTEL_TRUSTED_HOSTS=news-intelligence-ag.duckdns.org,127.0.0.1,localhost
NEWS_INTEL_CORS_ORIGINS=https://news-intelligence-ag.duckdns.org
# Optional demo read-only:
# NEWS_INTEL_DEMO_READ_ONLY=true
# NEWS_INTEL_DEMO_HOSTS=news-intelligence-ag.duckdns.org
```

Restart API after changes.

---

## Anti-patterns (caused prior outages)

| Mistake | Symptom |
|---------|---------|
| Port-forward **443 → Widow** while Caddy on PopOS also binds 443 | Only one host can receive WAN 443; breaks Open WebUI or NI |
| **`news-intelligence-ag` block commented out** in Caddyfile | TLS internal error — Caddy has no cert/site for that hostname |
| nginx upstream **`192.168.93.99:8000`** (old PopOS API) | Public site hits dead API |
| Expecting Widow **certbot** for public trust while Caddy fronts WAN | Browser sees Caddy's cert, not Widow's self-signed |

---

## Commands (cheat sheet)

```bash
# Verify public endpoints (from any LAN machine)
curl -sf https://news-intelligence-ag.duckdns.org/api/system_monitoring/health
curl -sf -o /dev/null -w '%{http_code}\n' https://legion-agent.duckdns.org/

# Verify Widow backend directly
curl -sfk https://192.168.93.101/ -H 'Host: news-intelligence-ag.duckdns.org'

# Reload Caddy after Caddyfile change (on PopOS)
docker exec ai-lab-caddy caddy reload --config /etc/caddy/Caddyfile
```

**Related:** [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) · [DYNAMIC_DNS_WIDOW.md](DYNAMIC_DNS_WIDOW.md) · [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) · HomeLab [PUBLIC_HTTPS_ROUTING.md](../../HomeLab-AI-Stack/docs/PUBLIC_HTTPS_ROUTING.md)
