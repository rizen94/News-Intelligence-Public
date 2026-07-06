# Platform requirements

## Supported

| Platform | Support | Notes |
|----------|---------|-------|
| Linux x86_64 | Primary | Native Docker |
| WSL2 Ubuntu | Primary | Preferred Windows path |
| macOS Apple Silicon | Best-effort | Use `compose.mac-host-ollama.yaml` |
| Windows native | **Not supported** | Must use WSL2 bootstrap |

## Hardware tiers

Set `KIT_HARDWARE_TIER` in `.env`:

| Tier | RAM | GPU | Models pulled |
|------|-----|-----|---------------|
| `minimal` | 8 GB | Optional | llama3.1:8b, nomic-embed-text |
| `standard` | 16 GB | Recommended | + phi3.5 |
| `performance` | 32 GB+ | NVIDIA | + mistral-nemo:12b |

## GPU matrix

| Vendor | Compose profile | Notes |
|--------|-----------------|-------|
| NVIDIA | `compose.gpu-nvidia.yaml` | Requires nvidia-container-toolkit |
| None | `compose.cpu-only.yaml` | Slower LLM; usable for setup + light ingest |
| macOS | `compose.mac-host-ollama.yaml` | Ollama on host, not in container |

Detection: `./scripts/detect_platform.sh` writes `platform.json`.

## Disk

- Postgres data: grows with articles (plan for 10–30 GB)
- Ollama models: 5–20 GB depending on tier
- Vault: small (markdown notes)

## Network

Outbound HTTPS required for RSS feeds and Ollama model pulls. No inbound ports except those you expose (8080, 3001, optional 11434).
