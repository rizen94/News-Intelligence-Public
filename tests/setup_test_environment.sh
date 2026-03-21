#!/bin/bash
"""
Setup script for test environment
"""

echo "🔧 SETTING UP TEST ENVIRONMENT"
echo "=============================="

# Install test requirements
echo "📦 Installing test requirements..."
pip install -r requirements.txt

# Set up test database (if needed)
echo "🗄️ Setting up test database..."
# Add database setup commands here if needed

# Verify API is running
echo "🌐 Verifying API is running..."
if curl -s http://localhost:8001/api/system_monitoring/status > /dev/null; then
    echo "✅ API is running on port 8001"
else
    echo "❌ API is not running. Please start the API server first."
    exit 1
fi

# Verify database is accessible
echo "🗄️ Verifying database connection..."
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        database='news_intelligence',
        user='newsapp',
        password='newsapp_password',
        port='5432'
    )
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
"

echo "✅ Test environment setup complete!"
echo ""
echo "🚀 Ready to run tests:"
echo "  python3 run_tests.py                    # Run all tests"
echo "  python3 run_tests.py --pattern <pattern> # Run specific tests"
