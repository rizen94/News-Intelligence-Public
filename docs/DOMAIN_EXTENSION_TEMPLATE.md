# Domain extension template

**Concept:** One **onboarding YAML** per optional domain (`api/config/domains/{domain_key}.yaml`) plus one **mechanical integration path** (SQL migration, [`api/scripts/provision_domain.py`](../api/scripts/provision_domain.py), verify scripts, frontend `domainHelper`). Built-in domains **politics**, **finance**, **science-tech** always exist; new silos extend the same article → processing → storyline pipeline.

**`public.domains` constraints** (see [`122_domain_silo_infrastructure.sql`](../api/database/migrations/archive/historical/122_domain_silo_infrastructure.sql) in **archive/historical**):

| Column / concept | Rule |
|------------------|------|
| `domain_key` | Required. `^[a-z0-9-]+$` — hyphens allowed; **no** underscores in the URL key. |
| `schema_name` | Required. `^[a-z0-9_]+$` — map `science-tech` → `science_tech`. |
| `name` | `VARCHAR(100)` — **display_name in YAML must be ≤ 100 characters.** |
| `description` | `TEXT` — recommend keeping under ~4k chars for readability. |
| `display_order` | Integer; lower = earlier when UIs sort by it. |

**Operator entry points**

- **Field rules & loader behavior:** [`api/config/domains/README.md`](../api/config/domains/README.md)
- **Example YAML (copy, do not deploy as-is):** [`api/config/domains/_template.example.yaml`](../api/config/domains/_template.example.yaml)
- **Registry (Python):** [`api/shared/domain_registry.py`](../api/shared/domain_registry.py)

---

**YAML conventions**

- Use **UTF-8**; quote scalars that contain `:` or `#`.
- **Unknown keys** are safe to add for runbooks; see README **“What code consumes today”** vs documentation-only fields.
- Keys starting with **`_`** are **human-only** and stripped by `domain_registry` (never read by logic).

## Validate onboarding YAML (before migrate)

From the **repository root**:

```bash
uv run python -c "
import yaml, pathlib, sys
p = pathlib.Path('api/config/domains/your-domain.yaml')
yaml.safe_load(p.read_text(encoding='utf-8'))
print('OK:', p)
"
```

Replace `your-domain.yaml` with your file. Fix encoding/syntax errors before running `provision_domain`.

**Optional later:** a JSON Schema for onboarding YAML can be added under `api/config/domains/` and checked in CI (not required for this doc pass).

---

## Order of operations (high level)

Detailed steps match [`api/config/domains/README.md` § How to use](../api/config/domains/README.md). Summary:

1. Copy `_template.example.yaml` → `{domain_key}.yaml`, set `is_active: false`.
2. Run the YAML validation one-liner above.
3. Author and apply the SQL migration (`public.domains`, `CREATE SCHEMA`, silo tables — see [`122_domain_silo_infrastructure.sql`](../api/database/migrations/archive/historical/122_domain_silo_infrastructure.sql) helpers).
4. Run `provision_domain.py` with `--config`, `--sql`, and `--verify-cmd` (see script docstring).
5. On success: `is_active: true`, restart API, update `web/src/utils/domainHelper.ts`.

---

## Related documentation

- **Agent / terminology:** [`AGENTS.md`](../AGENTS.md)
- **Deployment & DB:** [`docs/SETUP_ENV_AND_RUNTIME.md`](SETUP_ENV_AND_RUNTIME.md), [`docs/ARCHITECTURE_AND_OPERATIONS.md`](ARCHITECTURE_AND_OPERATIONS.md), [`docs/SECURITY_OPERATIONS.md`](SECURITY_OPERATIONS.md)

---

## Out of scope here

Domain-specific product features (e.g. court APIs) belong in feature docs; optional domains only need the **silo shell** + YAML above.
