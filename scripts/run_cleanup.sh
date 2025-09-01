#!/bin/bash
# Automated Cleanup Script for News Intelligence System
# Generated on 2025-08-28 20:49:26

cd /home/petes/news-system

# Run cleanup based on day of week
DAY_OF_WEEK=$(date +%u)

case $DAY_OF_WEEK in
    1) # Monday - Weekly cleanup
        python3 api/scripts/automated_cleanup.py weekly
        ;;
    2|3|4|5|6) # Tuesday-Friday - Daily cleanup
        python3 api/scripts/automated_cleanup.py daily
        ;;
    7) # Sunday - Light cleanup
        python3 api/scripts/automated_cleanup.py auto
        ;;
esac

# Log completion
echo "$(date): Cleanup completed" >> /var/log/news-system-cleanup.log
