#!/usr/bin/env bash
# Install and configure PgBouncer on Widow (Debian/Ubuntu) for news_intel.
# Run as root: sudo ./scripts/install_pgbouncer_widow.sh
#
# - Builds /etc/pgbouncer/userlist.txt from PostgreSQL pg_authid (SCRAM) for role newsapp.
# - Listens on 0.0.0.0:6432 → PostgreSQL 127.0.0.1:5432
# - Sets newsapp statement_timeout at ROLE level (app startup "options" ignored by PgBouncer).
#
# After install: set DB_PORT=6432 (and pool env vars) in /opt/news-intelligence/.env, then
#   sudo systemctl restart news-intelligence-api-public newsplatform-secondary

set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

STATEMENT_TIMEOUT_MS="${STATEMENT_TIMEOUT_MS:-120000}"
if ! [[ "$STATEMENT_TIMEOUT_MS" =~ ^[0-9]+$ ]]; then
  echo "STATEMENT_TIMEOUT_MS must be numeric (milliseconds)"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y pgbouncer

install -d -m 0755 /etc/pgbouncer

USERLIST_LINE="$(runuser -u postgres -- psql -d postgres -v ON_ERROR_STOP=1 -tAc \
  "SELECT format('\"%s\" \"%s\"', rolname, replace(rolpassword, '\"', '')) FROM pg_authid WHERE rolname='newsapp' AND rolpassword IS NOT NULL;")"
if [[ -z "${USERLIST_LINE// /}" ]]; then
  echo "ERROR: Could not read SCRAM secret for newsapp from pg_authid (role missing or empty password?)."
  exit 1
fi
printf '%s\n' "$USERLIST_LINE" > /etc/pgbouncer/userlist.txt
chown root:postgres /etc/pgbouncer/userlist.txt
chmod 0640 /etc/pgbouncer/userlist.txt

tee /etc/pgbouncer/pgbouncer.ini > /dev/null <<'INI'
[databases]
news_intel = host=127.0.0.1 port=5432 dbname=news_intel

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
unix_socket_dir = /var/run/postgresql
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 200
default_pool_size = 18
reserve_pool_size = 5
min_pool_size = 2
ignore_startup_parameters = extra_float_digits,options
admin_users = postgres
stats_users = postgres
logfile = /var/log/postgresql/pgbouncer.log
pidfile = /var/run/postgresql/pgbouncer.pid
server_reset_query = DISCARD ALL
INI
chown root:postgres /etc/pgbouncer/pgbouncer.ini
chmod 0644 /etc/pgbouncer/pgbouncer.ini

touch /var/log/postgresql/pgbouncer.log
chown postgres:postgres /var/log/postgresql/pgbouncer.log

# Preserve statement_timeout after ignoring startup "options" from clients.
runuser -u postgres -- psql -d postgres -v ON_ERROR_STOP=1 -c \
  "ALTER ROLE newsapp SET statement_timeout = '${STATEMENT_TIMEOUT_MS}ms';"

systemctl daemon-reload
systemctl enable pgbouncer
systemctl restart pgbouncer
sleep 1
systemctl --no-pager --full status pgbouncer || true

echo ""
echo "PgBouncer listening on :6432 (transaction pool → 127.0.0.1:5432)."
echo "Point apps at DB_PORT=6432. Restart API and secondary worker when ready."
echo "Admin: psql -h 127.0.0.1 -p 6432 -U postgres pgbouncer -c 'SHOW POOLS;'"
