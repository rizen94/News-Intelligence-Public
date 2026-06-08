# Domain onboarding specs (JSON)

**Source of truth** for optional YAML-onboarded silos. Runtime still loads `api/config/domains/{domain_key}.yaml` (generated).

| File | Purpose |
|------|---------|
| `domain.spec.schema.json` | JSON Schema for editors/CI |
| `_template.domain.json` | Copy for new domains |
| `{domain_key}.domain.json` | One manifest per silo |
| `generated/` | Optional synthesis stubs from generator |

## Workflow

```bash
# New domain
cp api/config/domains/specs/_template.domain.json api/config/domains/specs/my-domain.domain.json
# edit JSON

PYTHONPATH=api uv run python api/scripts/validate_domain_spec.py --spec api/config/domains/specs/my-domain.domain.json
PYTHONPATH=api uv run python api/scripts/generate_domain_artifacts.py \
  --spec api/config/domains/specs/my-domain.domain.json --migration-number NNN --force

PYTHONPATH=api uv run python api/scripts/provision_domain.py \
  --spec api/config/domains/specs/my-domain.domain.json \
  --sql api/database/migrations/NNN_my_domain_domain_silo.sql \
  --verify-cmd "PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py" \
  --ack-backup
```

See [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](../../../docs/DOMAIN_EXTENSION_TEMPLATE.md).
