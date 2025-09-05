#!/bin/bash

echo "=== FIXING ALL PATH IMPORTS ==="

# Fix @/utils/ imports
find web/src -name "*.ts" -o -name "*.tsx" | xargs sed -i 's|@/utils/|../utils/|g'

# Fix @/components/ imports
find web/src -name "*.ts" -o -name "*.tsx" | xargs sed -i 's|@/components/|../components/|g'

# Fix @/services/ imports
find web/src -name "*.ts" -o -name "*.tsx" | xargs sed -i 's|@/services/|../services/|g'

# Fix @/hooks/ imports
find web/src -name "*.ts" -o -name "*.tsx" | xargs sed -i 's|@/hooks/|../hooks/|g'

# Fix @/stores/ imports
find web/src -name "*.ts" -o -name "*.tsx" | xargs sed -i 's|@/stores/|../stores/|g'

# Fix @/types/ imports
find web/src -name "*.ts" -o -name "*.tsx" | xargs sed -i 's|@/types/|../types/|g'

# Fix @/contexts/ imports
find web/src -name "*.ts" -o -name "*.tsx" | xargs sed -i 's|@/contexts/|../contexts/|g'

# Fix @/pages/ imports
find web/src -name "*.ts" -o -name "*.tsx" | xargs sed -i 's|@/pages/|../pages/|g'

echo "Import fixes completed!"

