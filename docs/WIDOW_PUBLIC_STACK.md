# Widow + public HTTPS (nginx)

**Recommended:** **AutomationManager and the full FastAPI app run only on the main GPU machine.** Widow terminates TLS and serves static **`web/dist`**; **`/api/`** proxies to that host.

**Pieces:** Router → **Widow:80/443** (nginx) → **`web/dist`** + **`/api/`** → FastAPI on **main PC** (`PUBLIC_API_UPSTREAM`).

## Where the API should run

| Pattern | When |
|---------|------|
| **nginx on Widow → API on main GPU host** (**default**) | Set **`PUBLIC_API_UPSTREAM=192.168.x.x:8000`** (main PC LAN IP). Main uvicorn should bind **`0.0.0.0:8000`** or at least be reachable from Widow. Run **`sudo ./scripts/widow_disable_public_api.sh`** on Widow to stop **`news-intelligence-api-public`**. |
| **news-intelligence-api-public on Widow** | **Not recommended** — duplicates AutomationManager if the main API is also running. Only for a dedicated lab with **one** API instance total. |

DB-adjacent cron on Widow (RSS + sync) is separate; see **[WIDOW_DB_ADJACENT_CRON.md](WIDOW_DB_ADJACENT_CRON.md)**.

## Commands (cheat sheet)

```bash
# Reconfigure nginx (hostname + API on main PC)
export PUBLIC_DEMO_HOSTNAME=mydemo.duckdns.org
export PUBLIC_API_UPSTREAM=192.168.93.99:8000   # example: main machine
sudo bash ./scripts/widow_setup_public_nginx.sh

# On Widow: disable local FastAPI if it was enabled
sudo ./scripts/widow_disable_public_api.sh

# Deploy SPA from dev machine
./scripts/deploy_public_demo_to_widow.sh

# TLS after router + DNS work
sudo certbot --nginx -d mydemo.duckdns.org --agree-tos -m you@example.com
```

**Related:** [DYNAMIC_DNS_WIDOW.md](DYNAMIC_DNS_WIDOW.md) · [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) · [WIDOW_DB_ADJACENT_CRON.md](WIDOW_DB_ADJACENT_CRON.md)
