#!/bin/bash
# Simple API Restart Script
# Reliably stops and restarts the API server

echo "🔄 RESTARTING API SERVER (SIMPLE MODE)"
echo "====================================="

# Stop all API processes
echo "🛑 Stopping API server..."
pkill -9 -f "main_v4.py" 2>/dev/null || echo "No main_v4 process found"
pkill -9 -f "uvicorn" 2>/dev/null || echo "No uvicorn process found"
pkill -9 -f "start_dev_api.py" 2>/dev/null || echo "No dev API process found"
pkill -9 -f "start_prod_api.py" 2>/dev/null || echo "No prod API process found"
sleep 5

# Clear Python cache completely
echo "🧹 Clearing Python cache..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Cache cleared"

# Start API server with simple method
echo "🚀 Starting API server..."
cd "/home/pete/Documents/projects/Projects/News Intelligence"
source .venv/bin/activate
cd api

# Set environment variables
export DB_HOST=localhost
export DB_NAME=news_intelligence
export DB_USER=newsapp
export DB_PASSWORD=newsapp_password
export DB_PORT=5432

# Start with simple uvicorn command
uvicorn main_v4:app --host 0.0.0.0 --port 8001 --log-level info &
sleep 15

# Test the API
echo "🧪 Testing API..."
curl -s "http://localhost:8001/api/v4/system-monitoring/status" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if data.get('success'):
        print('✅ API Response:')
        print(f'Overall Status: {data[\"data\"][\"overall_status\"]}')
        print(f'CPU: {data[\"data\"][\"system\"][\"cpu_percent\"]}%')
        print(f'Memory: {data[\"data\"][\"system\"][\"memory_percent\"]}%')
        print(f'Disk: {data[\"data\"][\"system\"][\"disk_percent\"]}%')
        
        # Check GPU data
        system_data = data['data']['system']
        if 'gpu_vram_percent' in system_data:
            print(f'✅ GPU VRAM: {system_data[\"gpu_vram_percent\"]}%')
        else:
            print('❌ GPU VRAM data missing')
            
        if 'gpu_utilization_percent' in system_data:
            print(f'✅ GPU Utilization: {system_data[\"gpu_utilization_percent\"]}%')
        else:
            print('❌ GPU Utilization data missing')
            
        print()
        print('System Data Keys:', list(system_data.keys()))
    else:
        print(f'❌ API issue: {data}')
except Exception as e:
    print(f'Error: {e}')
"

echo "🎯 API server restart complete!"
