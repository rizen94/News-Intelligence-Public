"""
Root pytest configuration for News Intelligence System.
Adds api/ to sys.path so imports like 'from shared.database import ...' work
during tests regardless of working directory.
"""
import os
import sys

# Add the api/ directory to sys.path so intra-api bare imports work
# e.g., "from shared.X import Y", "from services.Z import W"
API_ROOT = os.path.join(os.path.dirname(__file__), "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)
