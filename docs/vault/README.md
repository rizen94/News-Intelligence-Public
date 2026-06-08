# Obsidian vault sync (News Intelligence)

The Obsidian MCP server reads **`/vault`** inside its container. Canonical vault root on this setup:

```bash
VAULT_ROOT="/mnt/obsidian-vault"
```

This repo keeps **mirrored** notes under `docs/vault/` for git tracking.

## Sync to vault

```bash
VAULT_ROOT="/mnt/obsidian-vault"

cp docs/vault/20_Projects/*.md "$VAULT_ROOT/20_Projects/" 2>/dev/null || true
cp docs/vault/30_Decisions/*.md "$VAULT_ROOT/30_Decisions/" 2>/dev/null || true
cp docs/vault/40_Reference/*.md "$VAULT_ROOT/40_Reference/" 2>/dev/null || true
cp docs/vault/10_Runbooks/*.md "$VAULT_ROOT/10_Runbooks/" 2>/dev/null || true
```

After external edits, run **`mempalace_reconnect`** if you mine vault content into MemPalace.

## MemPalace

- **Wing:** `News Intelligence` or `news_intelligence`
- **Search:** `mempalace_search` with query `widow migration` or `project boundaries`

## Key vault notes (June 2026)

| Path | Content |
|------|---------|
| `20_Projects/news-intelligence.md` | Production on Widow, cold storage |
| `30_Decisions/2026-06-06-ni-widow-migration-complete.md` | Migration ADR |
| `40_Reference/project-boundaries-ni-homelab.md` | NI vs Homelab split |
