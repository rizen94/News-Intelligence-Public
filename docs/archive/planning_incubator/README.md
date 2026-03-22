# Planning incubator (incorporation candidates)

These documents describe **work that was written up but not implemented as-spec** in the current v8 codebase. They stay in git as **design inventory** — not the live contract (use `DATABASE.md`, `API_REFERENCE.md`, `PIPELINE_AND_ORDER_OF_OPERATIONS.md` for that).

| Document | Intent | Incorporate when |
|----------|--------|------------------|
| [WEB_PRODUCT_DISPLAY_PLAN.md](WEB_PRODUCT_DISPLAY_PLAN.md) | Dashboard / navigation / product surface | Revisit when planning major UI IA changes |
| [PDF_INGESTION_ENHANCEMENT_PLAN.md](PDF_INGESTION_ENHANCEMENT_PLAN.md) | DB-backed PDF sources, discovery queue, QA | When hardening document ingestion beyond current `document_processing_service` |
| [V6_QUALITY_FIRST_UPGRADE_PLAN.md](V6_QUALITY_FIRST_UPGRADE_PLAN.md) | Older quality-first automation/orchestration ideas | When auditing phase ordering or quality gates — mine for ideas, do not treat as current spec |

**Tag:** `TAG_INCORPORATE` — merge ideas into active docs/code deliberately; do not resurrect wholesale without reconciling with v8 `AutomationManager` and flat `/api` routes.
