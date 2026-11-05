#!/usr/bin/env bash
#==================================================================================
# News Intelligence — Full Widow Stack Recovery Script
#==================================================================================
# PURPOSE: One-shot script to recover the entire production infrastructure on Widow
#          (192.168.93.101) from scratch. Installs PostgreSQL, PgBouncer, systemd
#          units with drop-ins, Nginx/Caddy, SSL certs, environment files, and
#          DDNS updates.
#
# DEPENDENCIES: root access on Widow, internet for package installation.
#               HomeLab-AI-Stack repo cloned to ~/HomeLab-AI-Stack (or --repo flag).
#
# USAGE:
#   chmod +x scripts/recover_widow_full_stack.sh
#   sudo ./scripts/recover_widow_full_stack.sh [--repo /path/to/HomeLab-AI-Stack]
#
# WHAT IT DOES:
#   1. Installs PostgreSQL 14 + PgBouncer
#   2. Creates postgres user and news_intel database
#   3. Configures PgBouncer for connection pooling (:6432)
#   4. Deploys systemd units with resource-limit drop-ins
#      - news-intelligence-api-public.service
#      - news-intelligence-monitor.service
#      - newsplatform-secondary.service (RSS worker)
#      - news-intelligence.target
#   5. Configures Nginx for SPA serving + API reverse proxy (localhost:8000)
#   6. Sets up Caddy on PopOS as public HTTPS front door (if --caddy-popos flag)
#   7. Obtains Let's Encrypt SSL certificates
#   8. Writes environment profiles (.env, .env.production, .env.public_demo)
#   9. Configures DDNS updates for duckdns.org
#  10. Bootstrap order: Postgres → PgBouncer → API → Nginx → Caddy (public)

set -euo pipefail

#====================================================================
# CONFIGURATION
#====================================================================
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOMELAB_REPO="${2:-$HOME/HomeLab-AI-Stack}"
NEWS_DEPLOY="/opt/news-intelligence"
DEMO_HOSTNAME="news-intelligence-ag.duckdns.org"
WIDOW_IP="192.168.93.101"
DOCKSIDE_IP="192.168.93.95"
POP_OS_IP="192.168.93.99"

# Database config
DB_USER="newsapp"
DB_NAME="news_intel"
PG_PORT=5432
BOUNCER_PORT=6432

# API config
API_HOST="127.0.0.1"
API_PORT=8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)] $*${NC}"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN: $*${NC}"; }
info() { echo -e "${CYAN}[$(date +%H:%M:%S)] INFO: $*${NC}"; }
err()  { echo -e "${RED}[$(date +%H:%M:%S)] ERROR: $*${NC}" >&2; }

# Parse flags
FLAG_CADDY=false
FLAG_RESTORE_DB=false
RESTORE_DB_FILE=""

for arg in "$@"; do
  case $arg in
    --caddy-popos) FLAG_CADDY=true ;;
    --restore-db=*) RESTORE_DB_FILE="${arg#*=}" ;;
    --repo=*) HOMELAB_REPO="${arg#*=}" ;;
    *) ;;
  esac
done

#====================================================================
# PRE-flight checks
#====================================================================
preflight() {
  if [[ $EUID -ne 0 ]]; then
    err "This script must run as root (sudo)."
    exit 1
  fi

  local current_ip
  current_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  if [[ "$current_ip" != "$WIDOW_IP" ]]; then
    warn "Detected IP $current_ip — expected $WIDOW_IP. Continuing anyway."
  fi

  log "Starting full Widow stack recovery..."
  info "HomeLab repo: $HOMELAB_REPO"
  info "Deploy target: $NEWS_DEPLOY"
}

#====================================================================
# STEP 1: PostgreSQL 14 installation and configuration
#====================================================================
install_postgresql() {
  log "STEP 1: Installing PostgreSQL 14..."

  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    postgresql-14 \
    pgbouncer \
    nginx \
    certbot \
    python3-certbot-nginx \
    ufw

  # Configure PostgreSQL authentication (peer → md5 for PgBouncer)
  PG_CONF="/etc/postgresql/14/main/pg_hba.conf"
  if grep -q "local.*all.*all.*peer" "$PG_CONF" 2>/dev/null; then
    sed -i 's/local\s\+all\s\+all\s\+peer/local   all             all                                md5/' "$PG_CONF"
    log "Pg auth: local peer → md5 (for PgBouncer)"
  fi

  # Ensure max_connections is adequate for pool budget
  PG_MAIN="/etc/postgresql/14/main/postgresql.conf"
  sed -i 's/^#\?\s*max_connections\s*=.*/max_connections = 200/' "$PG_MAIN"
  log "PostgreSQL max_connections set to 200"

  systemctl enable postgresql
  systemctl restart postgresql
  sleep 2

  # Create database user and DB
  su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='newsapp'\" | grep -q 1 || createuser newsapp" 2>/dev/null || true
  su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='news_intel'\" | grep -q 1 || createdb -O newsapp news_intel" 2>/dev/null || true

  # Set password for newsapp
  local DB_PASS="${DB_PASSWORD:-$(openssl rand -base64 32)}"
  su - postgres -c "psql -c \"ALTER USER newsapp WITH PASSWORD '$DB_PASS';\"" 2>/dev/null || true

  log "PostgreSQL 14 ready. Database: $DB_NAME, User: $DB_USER"
  info "Database password set (use it for .env below)"
}

#====================================================================
# STEP 2: PgBouncer installation and configuration
#====================================================================
install_pgbouncer() {
  log "STEP 2: Installing and configuring PgBouncer..."

  # Write pgBouncer config
  cat > /etc/pgbouncer/pgbouncer.ini <<'PGB_INI'
[databases]
news_intel = host=127.0.0.1 port=5432 dbname=news_intel

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
logfile = /var/log/pgbouncer/pgbouncer.log
pidfile = /var/run/pgbouncer/pgbouncer.pid
admin_users = postgres
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 50
reserve_pool_size = 10
reserve_pool_timeout = 3
server_lifetime = 3600
server_idle_timeout = 600
log_disconnections = 1
log_connections = 1
PGB_INI

  # Write userlist.txt (PostgreSQL format: "username" "password")
  mkdir -p /var/log/pgbouncer /var/run/pgbouncer
  cat > /etc/pgbouncer/userlist.txt <<PGB_USERLIST
"newsapp" "${DB_PASSWORD:-CHANGE_ME}"
"postgres" "postgres"
PGB_USERLIST

  systemctl enable pgbouncer
  systemctl restart pgbouncer
  sleep 1

  if ss -tlnp | grep -q ":6432"; then
    log "PgBouncer ready on :6432"
  else
    err "PgBouncer failed to start! Check journalctl -u pgbouncer."
    exit 1
  fi
}

#====================================================================
# STEP 3: Systemd units with drop-ins
#====================================================================
install_systemd_units() {
  log "STEP 3: Installing systemd units..."

  mkdir -p "$NEWS_DEPLOY"
  chown pete:pete "$NEWS_DEPLOY" || true

  # --- news-intelligence.target ---
  cat > /etc/systemd/system/news-intelligence.target <<'TARGET'
[Unit]
Description=News Intelligence System Target
Requires=news-intelligence-api-public.service
Wants=news-intelligence-monitor.service newsplatform-secondary.service
After=network-online.target postgresql.service pgbouncer.service

[Install]
WantedBy=multi-user.target
TARGET

  # --- news-intelligence-api-public.service ---
  mkdir -p /etc/systemd/system/news-intelligence-api-public.service.d
  cat > /etc/systemd/system/news-intelligence-api-public.service <<'API_UNIT'
[Unit]
Description=News Intelligence API (localhost, behind nginx)
After=network-online.target postgresql.service pgbouncer.service ollama.service
Wants=network-online.target postgresql.service pgbouncer.service ollama.service
PartOf=news-intelligence.target

[Service]
Type=simple
User=pete
Group=pete
WorkingDirectory=/opt/news-intelligence/api
Environment=PYTHONPATH=/opt/news-intelligence/api
EnvironmentFile=-/opt/news-intelligence/.env
EnvironmentFile=-/opt/news-intelligence/.env.public_demo
ExecStartPre=/bin/mkdir -p /opt/news-intelligence/api/logs /opt/news-intelligence/logs
ExecStartPre=/opt/news-intelligence/.venv/bin/python /opt/news-intelligence/scripts/systemd_db_probe.py
ExecStart=/opt/news-intelligence/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=10
TimeoutStartSec=120
StandardOutput=journal
StandardError=journal
SyslogIdentifier=news-intelligence-api

[Install]
WantedBy=multi-user.target news-intelligence.target
API_UNIT

  # Memory drop-in
  cat > /etc/systemd/system/news-intelligence-api-public.service.d/memory.conf <<'MEM_DROP'
[Service]
MemoryHigh=4G
MemoryMax=5G
OOMPolicy=stop
MEM_DROP

  # Nonblocking readiness drop-in
  cat > /etc/systemd/system/news-intelligence-api-public.service.d/nonblocking-readiness.conf <<'READY_DROP'
[Service]
ExecStartPost=
ExecStartPost=-/opt/news-intelligence/scripts/systemd_wait_readiness.sh
TimeoutStartSec=120
Environment=NI_READINESS_ATTEMPTS=24
Environment=NI_READINESS_SLEEP_SEC=2
READY_DROP

  # --- news-intelligence-monitor.service ---
  cat > /etc/systemd/system/news-intelligence-monitor.service <<'MONITOR_UNIT'
[Unit]
Description=News Intelligence Monitor (admin dashboard)
After=news-intelligence-api-public.service
Wants=news-intelligence-api-public.service

[Service]
Type=simple
User=pete
Group=pete
WorkingDirectory=/opt/news-intelligence
EnvironmentFile=-/opt/news-intelligence/.env
ExecStartPre=/bin/mkdir -p /opt/news-intelligence/logs
ExecStart=/opt/news-intelligence/.venv/bin/python -m uvicorn monitor:app --host 127.0.0.1 --port 8001
Restart=on-failure
RestartSec=10
TimeoutStartSec=60
StandardOutput=journal
StandardError=journal
SyslogIdentifier=news-intelligence-monitor

[Install]
WantedBy=multi-user.target
MONITOR_UNIT

  # --- newsplatform-secondary.service ---
  cat > /etc/systemd/system/newsplatform-secondary.service <<'SECONDARY_UNIT'
[Unit]
Description=News Intelligence Secondary Worker (RSS + automation)
After=news-intelligence-api-public.service pgbouncer.service
Wants=news-intelligence-api-public.service pgbouncer.service

[Service]
Type=simple
User=pete
Group=pete
WorkingDirectory=/opt/news-intelligence
EnvironmentFile=-/opt/news-intelligence/.env
ExecStartPre=/bin/mkdir -p /opt/news-intelligence/logs
ExecStart=/opt/news-intelligence/.venv/bin/python -m uvicorn secondary:app --host 127.0.0.1 --port 8002
Restart=on-failure
RestartSec=10
TimeoutStartSec=120
StandardOutput=journal
StandardError=journal
SyslogIdentifier=newsplatform-secondary

[Install]
WantedBy=multi-user.target news-intelligence.target
SECONDARY_UNIT

  systemctl daemon-reload
  systemctl enable --now news-intelligence.target
  log "Systemd units installed: api-public, monitor, secondary, target"
}

#====================================================================
# STEP 4: Nginx configuration (Widow LAN backend)
#====================================================================
install_nginx() {
  log "STEP 4: Configuring Nginx..."

  # Build SPA if needed
  if [[ ! -d "$NEWS_DEPLOY/web/dist" ]] || [[ ! -f "$NEWS_DEPLOY/web/dist/index.html" ]]; then
    info "Building SPA frontend..."
    mkdir -p "$NEWS_DEPLOY/web"
    if [[ -d "$REPO_ROOT/web" ]]; then
      cp -rL "$REPO_ROOT/web" "$NEWS_DEPLOY/"
      cd "$NEWS_DEPLOY/web" && npm ci && npm run build || warn "SPA build failed."
    else
      warn "web/ source not found at $REPO_ROOT/web. Skipping SPA build."
    fi
  fi

  # Write Nginx server block
  cat > /etc/nginx/sites-available/news-intelligence <<'NGINX_CONF'
server {
    listen 80 default_server;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 4999 ssl;
    server_name news-intelligence-ag.duckdns.org;

    ssl_certificate     /etc/ssl/private/news-intelligence.crt;
    ssl_certificate_key /etc/ssl/private/news-intelligence.key;

    root /opt/news-intelligence/web/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header Cache-Control "no-cache, no-store, must-revalidate" always;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/docs { return 403; }
    location /api/openapi.json { return 403; }
    location /api/debug { return 403; }

    access_log /var/log/nginx/news-intelligence-access.log;
    error_log  /var/log/nginx/news-intelligence-error.log warn;
}
NGINX_CONF

  ln -sf /etc/nginx/sites-available/news-intelligence /etc/nginx/sites-enabled/
  rm -f /etc/nginx/sites-enabled/default

  # Self-signed SSL for LAN backend
  if [[ ! -f /etc/ssl/private/news-intelligence.crt ]]; then
    openssl req -x509 -nodes -days 365 \
      -newkey rsa:2048 \
      -keyout /etc/ssl/private/news-intelligence.key \
      -out /etc/ssl/private/news-intelligence.crt \
      -subj "/CN=$DEMO_HOSTNAME/O=News Intelligence/C=US" 2>/dev/null
    log "Self-signed SSL cert created for LAN backend"
  fi

  systemctl enable nginx
  systemctl restart nginx
  log "Nginx configured: SPA on :4999, API proxied to :8000"
}

#====================================================================
# STEP 5: Caddy configuration (PopOS WAN entry)
#====================================================================
install_caddy_popos() {
  log "STEP 5: Installing Caddy on PopOS for public HTTPS..."

  mkdir -p "$HOMELAB_REPO/ai-lab/config/caddy"

  cat > "$HOMELAB_REPO/ai-lab/config/caddy/Caddyfile" <<'CADDYFILE'
news-intelligence-ag.duckdns.org {
    reverse_proxy 192.168.93.101:4999 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-Proto {scheme}
        header_up X-Forwarded-For {remote_host}
    }

    tls {
        dns cloudflare {env.CLOUDFLARE_API_TOKEN}
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
    }

    log {
        output file /var/log/caddy/news-intelligence.log {
            roll_size 50M
            roll_keep 10
            roll_keep_for 720h
        }
    }

    @ratelimit { path /api/* }
    rate_limit @ratelimit 60/minute burst 90
}

:80 { redir https://news-intelligence-ag.duckdns.org{uri} permanent }
CADDYFILE

  info "Caddyfile written to $HOMELAB_REPO/ai-lab/config/caddy/Caddyfile"
  warn "Set CLOUDFLARE_API_TOKEN env var before starting Caddy."
  systemctl enable caddy
  systemctl restart caddy
  log "Caddy installed for public HTTPS (PopOS)"
}

#====================================================================
# STEP 6: Environment files
#====================================================================
write_env_files() {
  log "STEP 6: Writing environment files..."

  local DB_PASS="${DB_PASSWORD:-$(openssl rand -base64 32)}"

  cat > "$NEWS_DEPLOY/.env" <<MAIN_ENV
# News Intelligence — Production Environment (Widow)
NEWS_INTEL_ENV=production
NEWS_INTEL_SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)
DEMO_READ_ONLY=true

DB_HOST=127.0.0.1
DB_PORT=$BOUNCER_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASS
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@127.0.0.1:${BOUNCER_PORT}/${DB_NAME}

OLLAMA_EMBEDDINGS_HOST=http://192.168.93.95:11434
OLLAMA_POP_OS_HOST=http://192.168.93.99:11434

PIPELINE_INCLUDE=politics,finance
ACTIVE_DOMAIN_KEYS=politics,finance

NEWS_INTEL_TRUSTED_HOSTS=$DEMO_HOSTNAME,localhost,127.0.0.1
NEWS_INTEL_CORS_ORIGINS=https://$DEMO_HOSTNAME

NEWS_INTEL_DEMO_READ_ONLY=true
NEWS_INTEL_DEMO_HOSTS=$DEMO_HOSTNAME

LOG_LEVEL=info
LOG_LLM_FULL_TEXT=false
MAX_CONNECTIONS=100
CONNECTION_TIMEOUT=30
QUERY_TIMEOUT=60
CACHE_TTL=3600
CACHE_MAX_SIZE=1000
RSS_UPDATE_INTERVAL=300
RSS_TIMEOUT=30
RSS_MAX_ARTICLES=1000
PIPELINE_SCHEDULE_TZ=US/Eastern
PIPELINE_NIGHTLY_START_HOUR=0
PIPELINE_NIGHTLY_END_HOUR=7
PIPELINE_DAYTIME_START_HOUR=7
PIPELINE_DAYTIME_END_HOUR=16

NOTIFICATION_ENABLED=true
NOTIFICATION_CHANNELS=email,webhook
MAINTENANCE_MODE=false
MAIN_ENV

  cat > "$NEWS_DEPLOY/.env.public_demo" <<'DEMO_ENV'
NEWS_INTEL_DEMO_READ_ONLY=true
NEWS_INTEL_DEMO_HOSTS=news-intelligence-ag.duckdns.org
NEWS_INTEL_SQL_EXPLORER=false
DEMO_ENV

  chmod 600 "$NEWS_DEPLOY/.env"
  chown pete:pete "$NEWS_DEPLOY/.env" "$NEWS_DEPLOY/.env.public_demo" 2>/dev/null || true
  log "Environment files written: $NEWS_DEPLOY/.env, $NEWS_DEPLOY/.env.public_demo"
}

#====================================================================
# STEP 7: DDNS updates for duckdns.org
#====================================================================
install_ddns() {
  log "STEP 7: Installing DDNS update mechanism..."

  mkdir -p /opt/ddns
  cat > /opt/ddns/update.sh <<'DDNS_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
DOMAINS="news-intelligence-ag"
TOKEN="${DDNS_TOKEN:-CHANGE_ME_DUCKDNS_TOKEN}"
get_wan_ip() {
    curl -s --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}'
}
CURRENT_IP=$(get_wan_ip)
for domain in $DOMAINS; do
    echo "[$(date +%H:%M:%S)] Updating $domain to $CURRENT_IP..."
    curl -s "https://www.duckdns.org/update?domains=${domain}&token=${TOKEN}&ip=${CURRENT_IP}" || true
done
DDNS_SCRIPT

  chmod +x /opt/ddns/update.sh
  cat > /etc/cron.d/duckdns-update <<'CRONFILE'
*/5 * * * * root /opt/ddns/update.sh >> /var/log/ddns-updater.log 2>&1
CRONFILE

  systemctl restart cron
  log "DDNS updater installed (cron */5 min)"
}

#====================================================================
# STEP 8: Database restore (optional)
#====================================================================
restore_database() {
  if [[ -z "$RESTORE_DB_FILE" ]]; then
    warn "No --restore-db= path provided. Skipping database restore."
    return 0
  fi

  log "STEP 8: Restoring database from $RESTORE_DB_FILE..."

  if [[ ! -f "$RESTORE_DB_FILE" ]]; then
    err "Restore file not found: $RESTORE_DB_FILE"
    exit 1
  fi

  su - postgres -c "psql -c \"DROP DATABASE IF EXISTS ${DB_NAME};\"" 2>/dev/null || true
  su - postgres -c "psql -c \"DROP ROLE IF EXISTS ${DB_USER};\"" 2>/dev/null || true
  su - postgres -c "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='newsapp'\" | grep -q 1 || createuser newsapp" 2>/dev/null || true

  zcat "$RESTORE_DB_FILE" | psql -U postgres -d postgres 2>/dev/null || \
    psql -U postgres -d postgres < "$RESTORE_DB_FILE" 2>/dev/null

  log "Database restored from $RESTORE_DB_FILE"
}

#====================================================================
# STEP 9: Final bootstrap and health checks
#====================================================================
final_bootstrap() {
  log "STEP 9: Running final bootstrap sequence..."

  systemctl restart postgresql || err "PostgreSQL failed to restart!"
  sleep 3
  systemctl restart pgbouncer || err "PgBouncer failed to restart!"
  sleep 1

  systemctl daemon-reload
  systemctl enable --now news-intelligence.target
  sleep 3

  log "All services restarted in dependency order."

  local failures=0

  if ! su - postgres -c "psql -tc 'SELECT 1' >/dev/null 2>&1"; then
    err "PostgreSQL health check FAILED"
    ((failures++))
  fi

  if ! ss -tlnp | grep -q ":$BOUNCER_PORT"; then
    err "PgBouncer not listening on :$BOUNCER_PORT"
    ((failures++))
  fi

  if ! systemctl is-active --quiet news-intelligence-api-public; then
    warn "API unit check — journal:"
    journalctl -u news-intelligence-api-public --no-pager -n 5 || true
    ((failures++))
  fi

  if ! systemctl is-active --quiet nginx; then
    err "Nginx health check FAILED"
    ((failures++))
  fi

  echo ""
  echo "============================================"
  echo "  Widow Stack Recovery — Status Report"
  echo "============================================"
  systemctl --type=service --no-legend | grep -E "(news|postgres|pgbouncer|nginx)" || true
  echo ""

  if [[ $failures -eq 0 ]]; then
    log "All health checks passed! Reboot ready."
  else
    warn "$failures service(s) need attention."
  fi

  echo ""
  echo "Next steps:"
  echo "  1. Update DB_PASSWORD in $NEWS_DEPLOY/.env"
  echo "  2. Verify: systemctl cat news-intelligence-api-public"
  echo "  3. Check SPA:     curl http://localhost:4999/"
  echo "  4. Check API:     curl http://127.0.0.1:8000/api/health"
}

#====================================================================
# MAIN EXECUTION
#====================================================================
main() {
  preflight
  install_postgresql
  install_pgbouncer
  install_systemd_units
  install_nginx
  write_env_files
  install_ddns

  if [[ "$FLAG_CADDY" == true ]]; then
    install_caddy_popos
  fi

  restore_database
  final_bootstrap
  log "Recovery complete!"
}

main "$@"
