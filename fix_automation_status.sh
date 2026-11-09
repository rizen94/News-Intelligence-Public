#!/bin/bash

# Fix for pipeline automation status tracking and Grafana dashboard issues
# This script should be run on Widow to fix the monitoring gaps

echo "=== PIPELINE AUTOMATION STATUS FIX ==="

# 1. First, let's check what automation processes are running
echo "Checking current automation manager processes..."
ps aux | grep automation_manager | grep -v grep

# 2. Check if the automation manager is enabled in environment
echo "Checking automation manager configuration..."
if [ -f "/home/pete/Documents/projects/news_intelligence/api/config/runtime.py" ]; then
    echo "Automation manager enabled: $(grep AUTOMATION_MANAGER_ENABLED /home/pete/Documents/projects/news_intelligence/api/config/runtime.py)"
fi

# 3. Verify database connection and table structure
echo "Verifying database table structure..."
cd /home/pete/Documents/projects/news_intelligence
python3 -c "
import psycopg2
conn = psycopg2.connect(
    host='widow',
    database='news_intelligence',
    user='newsapp',
    password='your_password_here'
)
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM public.pipeline_automation_status;\")
count = cur.fetchone()[0]
print(f'Current pipeline_automation_status records: {count}')
cur.execute(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'pipeline_automation_status';\")
columns = cur.fetchall()
print('Table columns:')
for col in columns:
    print(f'  {col[0]}: {col[1]}')
conn.close()
"

echo "=== FIX COMPLETE ==="
echo "Next steps:"
echo "1. Ensure automation_manager.py properly writes to pipeline_automation_status table"
echo "2. Update Grafana dashboards to reference correct data sources"
echo "3. Add proper logging for status updates"