#!/bin/bash
# News Intelligence — Setup application on Widow (secondary machine)
# Run ON Widow, or via: ssh widow "cd /opt/news-intelligence && ./scripts/setup_widow_app.sh"
# Creates venv, installs deps, writes .env, installs systemd + cron.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

WIDOW_USER="${WIDOW_USER:-$(whoami)}"

echo "Setting up News Intelligence on Widow at $PROJECT_DIR"

# 1. Python venv
if [ ! -d ".venv" ]; then
  echo "Creating Python venv..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r api/requirements.txt -q
echo "✅ Python environment ready"

# 2. .env for Widow (DB local; no Ollama)
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "Creating .env for secondary..."
  cat > "$ENV_FILE" << 'ENVEOF'
# Widow (secondary) — DB is local
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=news_intel
DB_USER=newsapp
DB_PASSWORD=
ENVIRONMENT=production
LOG_LEVEL=INFO
ENVEOF
  echo "⚠️  Edit .env and set DB_PASSWORD from .db_password_widow (or copy from primary)"
else
  echo "✅ .env exists (ensure DB_PASSWORD is set)"
fi

# 3. Load password if available
if [ -f "$PROJECT_DIR/.db_password_widow" ]; then
  PW=$(cat "$PROJECT_DIR/.db_password_widow")
  if grep -q '^DB_PASSWORD=$' "$ENV_FILE" 2>/dev/null || grep -q '^DB_PASSWORD=""$' "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^DB_PASSWORD=.*|DB_PASSWORD=$PW|" "$ENV_FILE"
    echo "✅ DB_PASSWORD set from .db_password_widow"
  fi
fi

# 4. Backup scripts executable
chmod +x "$SCRIPT_DIR/db_backup.sh" "$SCRIPT_DIR/db_backup_weekly.sh" 2>/dev/null || true
mkdir -p "$PROJECT_DIR/logs"

# 5. .pgpass for backup scripts (passwordless pg_dump)
if [ -f "$PROJECT_DIR/.db_password_widow" ]; then
  PW=$(cat "$PROJECT_DIR/.db_password_widow")
  echo "127.0.0.1:5432:news_intel:newsapp:$PW" > "$HOME/.pgpass"
  chmod 600 "$HOME/.pgpass"
  echo "✅ .pgpass created for backups"
fi

# 6. Systemd service
SVC_SRC="$PROJECT_DIR/infrastructure/newsplatform-secondary.service"
SVC_DEST="/etc/systemd/system/newsplatform-secondary.service"
if [ -f "$SVC_SRC" ]; then
  # Substitute REMOTE_DIR and USER in unit file
  sed "s|/opt/news-intelligence|$PROJECT_DIR|g; s|WIDOW_USER|$WIDOW_USER|g" "$SVC_SRC" | sudo tee "$SVC_DEST" > /dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable newsplatform-secondary
  echo "✅ Systemd service installed (not started yet — Phase 6)"
else
  echo "⚠️  $SVC_SRC not found; skipping systemd"
fi

# 7. Cron for backups (if cron.d template exists)
CRON_SRC="$PROJECT_DIR/infrastructure/newsplatform-backup.cron"
if [ -f "$CRON_SRC" ]; then
  sed "s|/opt/news-intelligence|$PROJECT_DIR|g; s|WIDOW_USER|$WIDOW_USER|g" "$CRON_SRC" | sudo tee /etc/cron.d/newsplatform-backup > /dev/null
  echo "✅ Backup cron installed"
fi

echo ""
echo "Setup complete. Verify:"
echo "  .venv/bin/python api/collectors/rss_collector.py  # Quick DB test"
echo "  ./scripts/db_backup.sh                            # Backup test"
