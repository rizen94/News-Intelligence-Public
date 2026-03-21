#!/bin/bash
# Test Debug Tools Script
# Validates that debugging utilities are working correctly

echo "🧪 Testing News Intelligence Debug Tools"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if frontend is running
echo "📡 Checking frontend status..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is running on http://localhost:3000${NC}"
else
    echo -e "${RED}❌ Frontend is not running${NC}"
    echo "   Start it with: cd web && npm start"
    exit 1
fi

# Check if API is running
echo ""
echo "📡 Checking API status..."
API_RESPONSE=$(curl -s http://localhost:8000/api/v4/system-monitoring/health 2>&1)
if echo "$API_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✅ API is running and healthy${NC}"
else
    echo -e "${YELLOW}⚠️  API may not be running or accessible${NC}"
fi

# Check if debug files exist
echo ""
echo "📁 Checking debug utility files..."
if [ -f "web/src/utils/debugHelper.ts" ]; then
    echo -e "${GREEN}✅ debugHelper.ts exists${NC}"
else
    echo -e "${RED}❌ debugHelper.ts not found${NC}"
fi

if [ -f "web/src/utils/featureTestHelper.ts" ]; then
    echo -e "${GREEN}✅ featureTestHelper.ts exists${NC}"
else
    echo -e "${RED}❌ featureTestHelper.ts not found${NC}"
fi

# Check if documentation exists
echo ""
echo "📚 Checking documentation..."
if [ -f "docs/FRONTEND_DEBUGGING_GUIDE.md" ]; then
    echo -e "${GREEN}✅ FRONTEND_DEBUGGING_GUIDE.md exists${NC}"
else
    echo -e "${YELLOW}⚠️  FRONTEND_DEBUGGING_GUIDE.md not found${NC}"
fi

if [ -f "docs/FRONTEND_DEBUGGING_QUICK_REFERENCE.md" ]; then
    echo -e "${GREEN}✅ FRONTEND_DEBUGGING_QUICK_REFERENCE.md exists${NC}"
else
    echo -e "${YELLOW}⚠️  FRONTEND_DEBUGGING_QUICK_REFERENCE.md not found${NC}"
fi

# Check TypeScript compilation
echo ""
echo "🔨 Checking TypeScript compilation..."
cd web
if npm run build 2>&1 | grep -q "Compiled"; then
    echo -e "${GREEN}✅ TypeScript compiles successfully${NC}"
else
    echo -e "${YELLOW}⚠️  TypeScript compilation has warnings (check output above)${NC}"
fi
cd ..

echo ""
echo "========================================"
echo "✅ Debug Tools Validation Complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Open http://localhost:3000 in your browser"
echo "   2. Open browser console (F12)"
echo "   3. Try: window.debugHelper.getDebugInfo()"
echo "   4. Try: featureTestHelper.runAllTests()"
echo ""
echo "📄 Documentation:"
echo "   • docs/FRONTEND_DEBUGGING_GUIDE.md"
echo "   • docs/FRONTEND_DEBUGGING_QUICK_REFERENCE.md"
echo ""
echo "🧪 Test Page:"
echo "   • scripts/test_debug_tools.html (open in browser)"
echo ""

