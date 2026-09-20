"""
News Intelligence Kit — FastAPI entry (wraps NI main + kit routes).

Run with PYTHONPATH=/app/api:/app/kit_api and NEWS_INTEL_KIT_MODE=true.
"""

from __future__ import annotations

import os
import sys

# Kit modules
_KIT_ROOT = os.path.dirname(os.path.abspath(__file__))
_APP_ROOT = os.path.dirname(_KIT_ROOT)
_NI_API = os.environ.get("NI_API_PATH", "/app/api")
for p in (_NI_API, _APP_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from config.runtime import env_bool, env_str  # noqa: E402

from kit_api.patches.kit_bootstrap import apply_kit_bootstrap  # noqa: E402

apply_kit_bootstrap()

# Import NI app factory
from main import app  # noqa: E402

from kit_api.routes.agent import router as agent_router  # noqa: E402
from kit_api.routes.kit_status import router as kit_status_router  # noqa: E402
from kit_api.routes.setup import router as setup_router  # noqa: E402
from kit_api.routes.vault import router as vault_router  # noqa: E402
from kit_api.services.setup_state import is_setup_complete  # noqa: E402
from kit_api.patches.domain_hardening import apply_domain_hardening  # noqa: E402

apply_domain_hardening()
from kit_api.patches.automation_gate import apply_automation_gate  # noqa: E402

apply_automation_gate()

from kit_api.middleware.setup_mode import SetupModeMiddleware  # noqa: E402

app.add_middleware(SetupModeMiddleware)

app.include_router(setup_router)
app.include_router(vault_router)
app.include_router(agent_router)
app.include_router(kit_status_router)


@app.get("/api/setup/complete")
async def setup_complete_flag() -> dict:
    return {"setup_complete": is_setup_complete()}


def _kit_automation_enabled() -> bool:
    if env_str("NEWS_INTEL_KIT_MODE", "true").lower() not in ("1", "true", "yes"):
        return True
    if env_bool("NEWS_INTEL_FORCE_AUTOMATION", False):
        return True
    return is_setup_complete()
