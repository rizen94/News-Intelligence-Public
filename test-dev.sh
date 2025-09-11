#!/bin/bash
# Test development environment

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Testing News Intelligence System v3.0 - Development Environment${NC}"
echo "====================================================================="

# Activate virtual environment
source .venv/bin/activate

# Test imports
echo "Testing imports..."
python -c "import fastapi; print('✅ FastAPI:', fastapi.__version__)"
python -c "import pydantic; print('✅ Pydantic:', pydantic.__version__)"
python -c "import sqlalchemy; print('✅ SQLAlchemy:', sqlalchemy.__version__)"

# Test API creation
echo ""
echo "Testing API creation..."
cd api
python -c "
import sys
sys.path.append('.')
from main import app
print('✅ API app created successfully')
"

# Test route imports
echo "Testing route imports..."
python -c "
from routes.health import router as health_router
from routes.articles import router as articles_router
from routes.pipeline_monitoring import router as pipeline_router
print('✅ All routes imported successfully')
"

echo ""
echo -e "${GREEN}✅ All development tests passed!${NC}"
echo ""
echo "Development environment is ready!"
echo "Run './start-dev.sh' to start the development server"
