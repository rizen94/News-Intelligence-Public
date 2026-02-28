#!/bin/bash
# Setup cron jobs for automated RSS collection
# Runs twice a day: 6 AM and 6 PM

echo "Setting up automated RSS collection cron jobs (twice daily)..."

# Create log directory
mkdir -p "$HOME/logs/news_intelligence"
LOG_DIR="$HOME/logs/news_intelligence"

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create cron job entries (twice daily: 6 AM and 6 PM)
CRON_JOBS="
# News Intelligence RSS Collection - Twice daily (6 AM and 6 PM)
0 6 * * * cd $PROJECT_DIR && DB_HOST=localhost DB_PORT=5433 .venv/bin/python api/collectors/rss_collector.py >> $LOG_DIR/rss_collection.log 2>&1
0 18 * * * cd $PROJECT_DIR && DB_HOST=localhost DB_PORT=5433 .venv/bin/python api/collectors/rss_collector.py >> $LOG_DIR/rss_collection.log 2>&1
"

# Remove any existing RSS collection cron jobs first
(crontab -l 2>/dev/null | grep -v "News Intelligence RSS Collection" | grep -v "rss_collector.py") | crontab -

# Add new cron jobs
(crontab -l 2>/dev/null; echo "$CRON_JOBS") | crontab -

echo "✅ Cron jobs installed successfully!"
echo ""
echo "📅 Collection schedule:"
echo "  - 6:00 AM (Morning)"
echo "  - 6:00 PM (Evening)"
echo ""
echo "📄 Logs will be written to: $LOG_DIR/rss_collection.log"
echo ""
echo "To view logs:"
echo "  tail -f $LOG_DIR/rss_collection.log"
echo ""
echo "To view current cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove cron jobs:"
echo "  crontab -l | grep -v 'News Intelligence RSS Collection' | crontab -"

