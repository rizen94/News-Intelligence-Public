# News Intelligence Kit

Portable, self-contained news intelligence stack: **Setup UI**, **Intake dashboard**, **Open WebUI agent**, Postgres, Ollama.

## Quick start (Linux / WSL)

```bash
cd news-intelligence-kit
chmod +x install.sh scripts/*.sh
./install.sh
# Open http://localhost:8080/setup/
```

## Windows

Double-click **`INSTALL-WINDOWS.bat`** (installs WSL2 + Docker Desktop if needed, then runs install inside Ubuntu).

## Surfaces

| URL | Purpose |
|-----|---------|
| http://localhost:8080/setup/ | First-run setup |
| http://localhost:8080/ | Intake SPA (dashboard, monitor, search) |
| http://localhost:3001/ | Open WebUI agent |

## After setup

```bash
./scripts/enable_automation.sh   # start pipeline
./scripts/repair.sh              # fix common issues
./scripts/backup_kit.sh          # backup DB + vault
```

See `docs/DEPLOY.md`, `docs/ENV_REFERENCE.md`, `docs/TROUBLESHOOTING.md`, `docs/INSTALL.md`.
