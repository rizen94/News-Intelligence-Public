# Home network: router as entry point (DDNS + port forwarding)

**Purpose:** Reach your demo from the internet when your **public IP changes**. The **router** is the normal **main entry point**: it owns the WAN address, receives **80/443**, and forwards to one internal machine running the reverse proxy.

**Terminology:** You need **Dynamic DNS (DDNS)** so a hostname (e.g. `mydemo.duckdns.org`) tracks your WAN IP. That is **not** the same as running a **recursive DNS resolver** on a server (Unbound/dnsmasq) — those don’t publish your home IP to the world.

---

## 1. Router-first layout (recommended)

| Role | Device |
|------|--------|
| **Internet entry point** | **Router** — only it has your public (WAN) IP on the outside. |
| **DDNS updates** | Prefer **router firmware** if it supports DuckDNS (or your provider). One place, no cron elsewhere. |
| **Port forwarding** | **Router:** WAN **TCP 80** and **443** → LAN IP of the host running **nginx/Caddy** (not necessarily Widow). |
| **TLS + SPA + `/api` proxy** | That internal host (often Widow or your app server). |
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
   | **80** | TCP | IP of **proxy host** | **80** |
   | **443** | TCP | same | **443** |

   Use the **LAN** address of the machine where Caddy/nginx listens (e.g. `192.168.93.x`), not the router’s own LAN IP unless the proxy literally runs on the router (unusual).

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

## 6. HTTPS on Widow (nginx)

Install **nginx** on the machine that receives **80/443** from the router (often Widow):

```bash
# On Widow, from repo (or copy template + script), set your real DuckDNS hostname:
export PUBLIC_DEMO_HOSTNAME=mydemo.duckdns.org
sudo bash ./scripts/widow_setup_public_nginx.sh
```

This configures **HTTP → HTTPS redirect** (port 80 is not used to serve the app), **ACME** path for Let’s Encrypt, **self-signed** TLS on 443 until you run **certbot** after the router and DNS work. Deploy **`web/dist`** to `/var/www/news-intelligence/web/dist`. Run the **FastAPI** process on **127.0.0.1:8000** on the same host so `/api/` proxies correctly.

**Replace the placeholder:** If you used a different `PUBLIC_DEMO_HOSTNAME` than your real DuckDNS name, re-run the script with the correct value or edit `/etc/nginx/sites-available/news-intelligence-public` and `sudo nginx -t && sudo systemctl reload nginx`.

**Related:** [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) · [WIDOW_DB_ADJACENT_CRON.md](WIDOW_DB_ADJACENT_CRON.md) · [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md)
