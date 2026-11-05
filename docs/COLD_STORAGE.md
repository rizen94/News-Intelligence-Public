# News Intelligence — cold storage pointer

The **PopOS local copy** of News Intelligence at `~/Documents/projects/News Intelligence` is **not authoritative**. It is scheduled for NAS cold storage.

## Active development (use these)

| Item | Location |
|------|----------|
| **Host** | Widow `192.168.93.101` |
| **Dev workspace** | `/home/pete/Documents/projects/News Intelligence` on Widow |
| **Production API** | `/opt/news-intelligence` on Widow (`:8000`) |
| **Access** | `ssh widow` or VS Code Remote SSH |

## Cold storage (NAS)

| Item | Path |
|------|------|
| **Archive folder** | `/mnt/nas/News-Intelligence-Archive-2026-06-03` |

## Documentation (survives cold storage)

| Store | Location |
|-------|----------|
| **Obsidian** | `/mnt/obsidian-vault/20_Projects/news-intelligence.md` |
| **MemPalace** | wing `news_intelligence`, rooms `infrastructure`, `database` |
| **Monorepo boundary** | `~/Documents/projects/PROJECT_BOUNDARIES.md` |
| **Homelab integration** | `HomeLab-AI-Stack/docs/NEWS_INTELLIGENCE_INTEGRATION.md` |

## NAS move (when ready)

```bash
# 1. Verify Widow has latest docs
rsync -av --include='*.md' --include='*/' --exclude='*' \
  "/home/pete/Documents/projects/News Intelligence/" \
  "widow:/home/pete/Documents/projects/News Intelligence/"

# 2. Copy to NAS cold storage
rsync -aH \
  "/home/pete/Documents/projects/News Intelligence/" \
  "/mnt/nas/News-Intelligence-Archive-2026-06-03/"

# 3. Verify NAS copy, then remove local (destructive)
# rm -rf "/home/pete/Documents/projects/News Intelligence"
```

Keep this stub file after removing the local folder.

## Related

- Widow: `PROJECT_STATUS.md` in the active repo
- [PROJECT_BOUNDARIES.md](PROJECT_BOUNDARIES.md)
