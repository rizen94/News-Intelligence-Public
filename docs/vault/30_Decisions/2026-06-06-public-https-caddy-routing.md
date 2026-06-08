# Decision: Public HTTPS via PopOS Caddy (June 2026)

## Context

Two public DuckDNS hostnames on one WAN IP (`73.167.39.74`):

- `legion-agent.duckdns.org` — HomeLab Open WebUI
- `news-intelligence-ag.duckdns.org` — News Intelligence public demo

## Decision

- **Router** forwards WAN **80/443 → PopOS** (`192.168.93.99`).
- **`ai-lab-caddy`** terminates **Let's Encrypt** TLS and routes by hostname.
- **News Intelligence** backend stays on **Widow** (`192.168.93.101` nginx → uvicorn `:8000`).
- **Do not** forward WAN 443 to Widow separately.

## Config

- Caddy: `HomeLab-AI-Stack/ai-lab/config/caddy/Caddyfile`
- Widow nginx: `/etc/nginx/sites-available/news-intelligence-public` (upstream `127.0.0.1:8000`)

## Docs

- NI: [WIDOW_PUBLIC_STACK.md](../../WIDOW_PUBLIC_STACK.md)
- HomeLab: [PUBLIC_HTTPS_ROUTING.md](../../../../HomeLab-AI-Stack/docs/PUBLIC_HTTPS_ROUTING.md)
