# Network / port registry pointer

News Intelligence binds the **FastAPI** server to host **`8000`** by default (**`frontend` → `3000`**). Homelab Postgres MCP SSE is published on **`18090`** by default so it does **not** take **`8000`**.

Canonical **published ports**, **Docker `ai-lab-net` internal ports**, **MCP SSE URLs**, and **cross-project overlaps** with this repo are maintained under the Home AI Lab stack:

[**`HomeLab-AI-Stack/docs/PORTS.md`**](../../HomeLab-AI-Stack/docs/PORTS.md)

News Intelligence defaults (backend **`8000`**, frontend **`3000`**, etc.) are summarized there beside HomeLab compose. Update **`configs/.env`** locally after any coordinated migration.
