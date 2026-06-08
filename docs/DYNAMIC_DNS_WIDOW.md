# Home network: router as entry point (DDNS + port forwarding)

**Purpose:** Reach your demo from the internet when your **public IP changes**. The **router** is the normal **main entry point**: it owns the WAN address, receives **80/443**, and forwards to one internal machine running the reverse proxy.

**Terminology:** You need **Dynamic DNS (DDNS)** so a hostname (e.g. `mydemo.duckdns.org`) tracks your WAN IP. That is **not** the same as running a **recursive DNS resolver** on a server (Unbound/dnsmasq) — those don’t publish your home IP to the world.

---

## 1. Router-first layout (recommended)

| Role | Device |
|------|--------|
| **Internet entry point** | **Router** — only it has your public (WAN) IP on the outside. |
| **DDNS updates** | Prefer **router firmware** if it supports DuckDNS (or your provider). One place, no cron elsewhere. |
| **Port forwarding** | **Router:** WAN **TCP 80** and **443** → LAN IP of **PopOS** (`192.168.93.99`) where **Caddy** listens. |
| **TLS + SPA + `/api` proxy** | **PopOS Caddy** terminates public TLS; **`news-intelligence-ag.duckdns.org`** → Widow nginx. **Widow** serves SPA + local `/api` on LAN. |
| **PostgreSQL / Ollama** | **Not** forwarded; LAN-only. |

Visitors: `https://mydemo.duckdns.org` → DNS → your **WAN IP** → **router** → forwarded to **proxy host:443**.

---

## 2. Configure the router (your steps)

1. **DDNS (on the router)**  
   In the admin UI, find **Dynamic DNS** / **DDNS** (sometimes under *Internet*, *WAN*, or *Advanced*).  
   - Provider: **DuckDNS** (or as close as the menu offers).  
   - Enter **subdomain** + **token** from [duckdns.org](https://www.duckdns.org/).  
   - Save; confirm the router shows “success” or updated IP.

2. **Port forwarding (on the same router)**  
   Find **Port forwarding** / **Virtual server** / **NAT**. Add:

   | WAN / external | Protocol | LAN IP | LAN port |
   |----------------|----------|--------|----------|
   | **80** | TCP | IP of **PopOS** (Caddy) | **80** |
   | **443** | TCP | IP of **PopOS** (Caddy) | **443** |

   Use **`192.168.93.99`** (PopOS), not Widow — Caddy proxies to Widow for NI. Open WebUI and NI share this entry point via hostname routing ([WIDOW_PUBLIC_STACK.md](WIDOW_PUBLIC_STACK.md)).

3. **Do not** forward **5432**, **11434**, or **8000** to the internet for this pattern.

4. **Double-updates:** If the router runs DDNS, **do not** also run the Widow DuckDNS script on a schedule — pick **one** updater.

---

## 3. Fallback: DDNS from Widow (no router DDNS)

If your router **does not** support DuckDNS (or DDNS fails):

1. Create `mydemo.duckdns.org` at [DuckDNS](https://www.duckdns.org/) and copy the token.
2. On Widow:

   ```bash
   cp configs/ddns.env.example configs/ddns.env
   chmod 600 configs/ddns.env
   # DUCKDNS_DOMAIN=mydemo  DUCKDNS_TOKEN=...
   ./scripts/ddns_update_duckdns.sh
   ```

3. Cron every 5 minutes — see script header. **Still** use the **router** for port forwarding **80/443** to the proxy host.

**Security:** `configs/ddns.env` is gitignored; never commit tokens.

---

## 4. App env alignment

Match your public hostname:

- `NEWS_INTEL_TRUSTED_HOSTS=mydemo.duckdns.org`
- `NEWS_INTEL_CORS_ORIGINS=https://mydemo.duckdns.org`

TLS (Caddy/certbot) on the **proxy host** once DNS points to your WAN IP and **80/443** reach that host through the router.

---

## 5. Troubleshooting

| Symptom | Check |
|---------|--------|
| Hostname doesn’t resolve or wrong IP | Router DDNS status; or run Widow script manually and confirm DuckDNS `OK`. |
| HTTPS timeout | Port-forward targets wrong LAN IP; proxy not listening on 443; ISP blocking 80/443 (rare). |
| Double DDNS conflict | Disable one of router DDNS vs Widow cron. |

TLS (Let's Encrypt via **PopOS Caddy**) on the **WAN entry host** once DNS points to your WAN IP and **80/443** reach PopOS. Widow nginx uses an internal cert for the Caddy→Widow hop; public browsers trust Caddy's certificate.

## 6. HTTPS — PopOS Caddy + Widow nginx (current)

**Public TLS:** `ai-lab-caddy` on PopOS — see HomeLab [PUBLIC_HTTPS_ROUTING.md](../../HomeLab-AI-Stack/docs/PUBLIC_HTTPS_ROUTING.md).

**Widow backend (LAN):** nginx serves **`web/dist`** and proxies **`/api/`** to **`127.0.0.1:8000`**. Optional initial setup:

```bash
# On Widow — LAN backend only (public cert is on PopOS Caddy)
export PUBLIC_DEMO_HOSTNAME=news-intelligence-ag.duckdns.org
export PUBLIC_API_UPSTREAM=127.0.0.1:8000
sudo bash ./scripts/widow_setup_public_nginx.sh
./scripts/deploy_public_demo_to_widow.sh
```

**Do not** run certbot on Widow for the public hostname unless Caddy is removed from the WAN path.

**Related:** [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) · [WIDOW_DB_ADJACENT_CRON.md](WIDOW_DB_ADJACENT_CRON.md) · [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md)
