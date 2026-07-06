# Installation

## Requirements

- Docker Engine 24+ and Docker Compose v2
- 16 GB RAM recommended (8 GB minimal with `KIT_HARDWARE_TIER=minimal`)
- 40 GB free disk for Postgres, Ollama models, and vault
- Linux or WSL2 on Windows (native Windows is not supported for runtime)

## Linux / WSL

```bash
cd news-intelligence-kit
chmod +x install.sh scripts/*.sh
./install.sh
```

Open **http://localhost:8080/setup/** and complete the wizard.

After setup:

```bash
./scripts/enable_automation.sh
./scripts/pull_ollama_models.sh
./scripts/smoke_test.sh
```

## Windows

See [WINDOWS_INSTALL.md](WINDOWS_INSTALL.md) — use `INSTALL-WINDOWS.bat`.

## Platform profiles

`install.sh` runs `detect_platform.sh` and may add:

| Profile | When |
|---------|------|
| `compose.gpu-nvidia.yaml` | NVIDIA GPU + drivers |
| `compose.mac-host-ollama.yaml` | macOS (host Ollama) |
| `compose.cpu-only.yaml` | No GPU |

See [PLATFORM_REQUIREMENTS.md](PLATFORM_REQUIREMENTS.md).

## Headless provision

```bash
docker compose exec api python3 /app/kit/scripts/provision_from_spec.py /app/kit/config/setup/smoke_domains.json
./scripts/enable_automation.sh
```
