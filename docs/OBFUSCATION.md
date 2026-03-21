# Documentation obfuscation (public repo hygiene)

**Purpose:** The committed **markdown** uses placeholders such as `<WIDOW_HOST_IP>` instead of fixed LAN addresses, so a public clone does not embed your network layout. Passwords must **never** appear in docs; use `DB_PASSWORD` in `.env` (gitignored) only.

---

## What is tokenized in docs

Common tokens (angle brackets, searchable):

| Token | Typical meaning |
|-------|------------------|
| `<PRIMARY_HOST_IP>` | Machine where the API / frontend run |
| `<WIDOW_HOST_IP>` | PostgreSQL host |
| `<NAS_HOST_IP>` | NAS / storage host |
| `<MONITORING_PI_IP>` | Optional Pi or edge device for monitoring SSH |
| `<OLLAMA_LAN_IP>` | Example LAN address for Ollama (if referenced) |
| `<EXAMPLE_PROJECT_ROOT>` | Example clone path in shell snippets |

Runtime config under `api/config/` (for example `monitoring_devices.yaml`) may still list **real** IPs so SSH and dashboards work on your LAN. Treat that file as **deployment-specific**; forks should replace hosts with their own addresses.

---

## Local mapping file (gitignored)

1. Copy `configs/doc_obfuscation.example.yaml` to **`configs/doc_obfuscation.local.yaml`** (this path is in `.gitignore`).
2. Set each `private` value to your real LAN IP or path. **Do not commit** this file.

The example file ships with **fictional** `private` values so the template is safe to commit.

---

## Scripts: expand vs scrub

From the project root (with `pyyaml` available, e.g. `uv sync`):

**Expand** — write a **read-only copy** under `docs/_local_expanded/` with `<TOKENS>` replaced by your local `private` values (useful for printing or internal notes). Output is gitignored.

```bash
PYTHONPATH=api uv run python scripts/doc_obfuscation.py expand --paths docs AGENTS.md QUICK_START.md
```

**Scrub** — replace real values with public tokens in a **single** file you pasted into (e.g. before sharing a snippet):

```bash
PYTHONPATH=api uv run python scripts/doc_obfuscation.py scrub --in draft.md --out safe.md
```

---

## Code and shell scripts

Many `.py` and `.sh` files still use **defaults or examples** with private LAN addresses or usernames. Before treating the repo as fully “sanitized,” run:

```bash
git grep -E '192\\.168\\.|10\\.0\\.' -- '*.py' '*.sh' '*.yaml' '*.yml'
```

Longer-term, prefer **`DB_HOST` in `.env`** and env-driven deploy scripts instead of hardcoded hosts.

---

## Related

- [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) — secrets and exposure
- [REPO_MAINTENANCE.md](REPO_MAINTENANCE.md) — what belongs in Git
