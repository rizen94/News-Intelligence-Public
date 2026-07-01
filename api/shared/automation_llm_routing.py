"""PopOS GPU + dual-lane routing for steady-state AutomationManager."""

from __future__ import annotations

from shared.pipeline_resource_policy import configure_pipeline_resources

# Re-export for callers that still import automation_llm_routing
configure_automation_extraction_routing = configure_pipeline_resources

__all__ = ["configure_automation_extraction_routing", "configure_pipeline_resources"]
