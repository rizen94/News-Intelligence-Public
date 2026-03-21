#!/bin/bash
# Setup cron jobs for automated RSS collection and ML processing
# Runs 4 times a day: 6 AM, 12 PM, 6 PM, 12 AM

echo "Setting up automated RSS collection cron jobs..."

# Create log directory
sudo mkdir -p /var/log/news_intelligence
sudo chown $USER:$USER /var/log/news_intelligence

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create cron job entries
CRON_JOBS="
# News Intelligence RSS Collection - 4 times daily
0 6 * * * cd $PROJECT_DIR && python3 api/scripts/automated_collection.py >> /var/log/news_intelligence/cron.log 2>&1
0 12 * * * cd $PROJECT_DIR && python3 api/scripts/automated_collection.py >> /var/log/news_intelligence/cron.log 2>&1
0 18 * * * cd $PROJECT_DIR && python3 api/scripts/automated_collection.py >> /var/log/news_intelligence/cron.log 2>&1
0 0 * * * cd $PROJECT_DIR && python3 api/scripts/automated_collection.py >> /var/log/news_intelligence/cron.log 2>&1
"

# Add to crontab
(crontab -l 2>/dev/null; echo "$CRON_JOBS") | crontab -

echo "Cron jobs installed successfully!"
echo "Collection schedule:"
echo "  - 6:00 AM (Morning)"
echo "  - 12:00 PM (Noon)" 
echo "  - 6:00 PM (Evening)"
echo "  - 12:00 AM (Midnight)"
echo ""
echo "Logs will be written to: /var/log/news_intelligence/"
echo "To view logs: tail -f /var/log/news_intelligence/cron.log"
echo "To view collection logs: tail -f /var/log/news_intelligence/collection.log"
