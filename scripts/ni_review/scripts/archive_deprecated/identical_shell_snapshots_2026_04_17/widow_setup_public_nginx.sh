#!/usr/bin/env bash
# Install nginx on Widow for public HTTPS demo: HTTP only redirects + ACME path; HTTPS serves SPA + /api.
# Run ON Widow with sudo, or: ssh pete@widow 'sudo bash -s' < scripts/widow_setup_public_nginx.sh
#
# Before first run, set your DuckDNS (or other) hostname:
#   export PUBLIC_DEMO_HOSTNAME=mydemo.duckdns.org
#
# After your router forwards 80/443 and DNS points here, replace the self-signed cert with Let's Encrypt:
#   sudo certbot --nginx -d "$PUBLIC_DEMO_HOSTNAME" --non-interactive --agree-tos --register-unsafely-without-email
# (Or provide -m you@example.com instead of --register-unsafely-without-email.)
#
set -euo pipefail

PUBLIC_DEMO_HOSTNAME="${PUBLIC_DEMO_HOSTNAME:-}"
if [[ -z "${PUBLIC_DEMO_HOSTNAME}" ]]; then
  echo "Set PUBLIC_DEMO_HOSTNAME, e.g. export PUBLIC_DEMO_HOSTNAME=mydemo.duckdns.org" >&2
  exit 1
fi

# Where uvicorn listens: 127.0.0.1:8000 on this host, OR e.g. 192.168.93.99:8000 if API runs on another machine.
PUBLIC_API_UPSTREAM="${PUBLIC_API_UPSTREAM:-127.0.0.1:8000}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx openssl

install -d -m 755 /var/www/news-intelligence/web/dist
install -d -m 755 /var/www/certbot
# Allow deploy user (e.g. pete) to rsync SPA builds without sudo
if [[ -n "${SUDO_USER:-}" ]] && id -u "${SUDO_USER}" &>/dev/null; then
  chown -R "${SUDO_USER}:${SUDO_USER}" /var/www/news-intelligence/web
fi

if [[ ! -f /var/www/news-intelligence/web/dist/index.html ]]; then
  cat > /var/www/news-intelligence/web/dist/index.html << 'HTML'
<!DOCTYPE html><html><head><meta charset="utf-8"><title>News Intelligence</title></head>
<body><p>SPA build not deployed yet. From dev: <code>cd web &amp;&amp; npm run build:bundle</code> then sync <code>web/dist</code> here.</p></body></html>
HTML
fi

CERT="/etc/ssl/certs/news-intelligence-demo-selfsigned.crt"
KEY="/etc/ssl/private/news-intelligence-demo-selfsigned.key"
if [[ ! -f "${CERT}" ]]; then
  openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout "${KEY}" \
    -out "${CERT}" \
    -subj "/CN=${PUBLIC_DEMO_HOSTNAME}/O=News Intelligence Demo"
  chmod 640 "${KEY}"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE="${WIDOW_PUBLIC_NGINX_TEMPLATE:-${REPO_ROOT}/nginx/widow-public-demo-site.conf.template}"
if [[ ! -f "${TEMPLATE}" ]]; then
  echo "Missing nginx template. Set WIDOW_PUBLIC_NGINX_TEMPLATE=/path/to/widow-public-demo-site.conf.template" >&2
  exit 1
fi

sed -e "s/PUBLIC_DEMO_HOSTNAME/${PUBLIC_DEMO_HOSTNAME}/g" \
    -e "s|SSL_CERT_PATH|${CERT}|g" \
    -e "s|SSL_KEY_PATH|${KEY}|g" \
    -e "s|API_UPSTREAM|${PUBLIC_API_UPSTREAM}|g" \
    "${TEMPLATE}" > /etc/nginx/sites-available/news-intelligence-public

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/news-intelligence-public /etc/nginx/sites-enabled/news-intelligence-public

nginx -t
systemctl enable nginx
systemctl restart nginx

echo ""
echo "nginx is listening on 80 (redirect + ACME) and 443 (HTTPS, self-signed for now)."
echo "Set NEWS_INTEL_TRUSTED_HOSTS / CORS to: ${PUBLIC_DEMO_HOSTNAME}"
echo "Upstream for /api/: ${PUBLIC_API_UPSTREAM} — ensure that process is reachable from this host."
echo "After router + DNS: sudo apt-get install -y certbot python3-certbot-nginx && sudo certbot --nginx -d ${PUBLIC_DEMO_HOSTNAME}"
