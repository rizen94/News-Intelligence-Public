# TTRPG PDF Extraction Pipeline

> **Location:** `/mnt/fortress2/ttrpg/` on fortress2
> **Pipeline:** `ttrpg-text-extract` (config: `projects/ttrpg-text-extract/book_types.yaml`, `corpus_filter.yaml`)
> **Manifest:** `manifest/CATALOG.md`, `manifest/catalog.json`, `manifest/catalog.csv`
> **Extracted DB:** `extracted/db/extract.sqlite`

---

## Summary

| Edition | Files Extracted | Status |
|---------|----------------|--------|
| D&D 5th Edition (5e) | 506 | complete |
| Pathfinder 1e | 1 | partial |
| SRD 5.2.1 (CC) | 1 | partial |
| **Total pages** | **1,232** | — |

---

## Core Rulebooks (Catalog Tracked)

| Book | Pages | Status |
|------|-------|--------|
| Player's Handbook (5e) | 322 | complete |
| Dungeon Masters Guide (5e) | 320 | complete |
| Volo's Guide to Monsters | 226 | complete |
| DnD SRD PH v1 (CC) | 364 | complete |

---

## Adventure Modules Extracted

### Official Wizards of the Coast
- **Curse of Strahd** (+ Death House + AL quests DDAL04-01 through DDAL04-14)
- **Baldur's Gate: Descent into Avernus** (+ Miscellany Set)
- **Tomb of Annihilation** (+ Maps)
- **Out of the Abyss** (+ Maps + WoTC edition)
- **Tyranny of Dragons** (Hoard of the Dragon Queen + Rise of Tiamat, Anniversary Edition)
- **Storm King's Thunder**
- **Ghosts of Saltmarsh**
- **Icewind Dale: Rime of the Frostmaiden**
- **The Wild Beyond the Witchlight** (+ Maps + Special Cover variant)
- **Candlekeep Mysteries** (DnD Beyond rip)
- **Waterdeep: Dragon Heist** (+ Background Hooks)
- **Waterdeep: Dungeon of the Mad Mage** (+ Maps & Miscellany)
- **Lost Mines of Phandelver**
- **Stranger Things Starter Set**

### Adventures in Middle-Earth
- Wilderland Adventures (endpapers, maps)
- The Eaves of Mirkwood (optional class rules)
- The Road Goes Ever On (maps)
- The Mirkwood Campaign (battlemaps)
- Eriador Adventures (maps)
- Erebor Adventures
- Loremaster's Guide (screen, region guides: Bree-land, Lonely Mountain, Rhovanion, Rivendell, Rohan)

---

## Player System Supplements

### Core PHB Extensions
- **Xanathar's Guide to Everything** (DDB rip + Deluxe variant)
- **Tasha's Cauldron of Everything** (HQ variants + Reduced Size + multiple cover versions)
- **Mordenkainen's Tome of Foes**
- **Sword Coast Adventurer's Guide**
- **Explorer's Guide to Wildemount** (Ravnica)
- **Mythic Odysseys of Theros**
- **Fizban's Treasury of Dragons** (HQ, OCR, Bookmarked)
- **Guildmasters' Guide to Ravnica** + Wayfinder's Guide to Eberron
- **Minsc & Boo's Guide to Stuff & Things**
- **Van Richten's Guide to Ravenloft** (+ variant spellings: Van Richtens Guide to Ranveloft)
- **Elemental Evil Player's Companion**

### Additional Sources
- **Basic Rules** (DM + Player variants, multiple versions 0.3–0.5–1.0)
- **Unearthed Arcana Compendium** (+ UA series: Psionics, Modern Magic, Eberron, Battlesystem, Ranger/Rogue, Artificer, Waterborne Adventures, Feats variant, etc.)
- **Sage Advice Compendium** v2.2

### Adventure League Content
- Convention Created Content (CCC-BMG series — Baldman Games core quests)
- Bleeding Gate supplemental
- Third Party AL content
- Eberron Oracle of War DM Guide

---

## Third-Party Settings

- **Trudvang** (Hero Companion, Setting Companion, The Great Shadow, Wildheart, Wurmtongue adventures)
- **Nerzugal's Tome of Horrifying Adventures** (5E Steven Williams)
- **Fateforge Corebook** (Adventurers)
- **Strixhaven - A Curriculum of Chaos** (HQ, OCR, Bookmarked, Optimized)
- **Grim Hollow Campaign Guide** (PDF)
- **Svilland Campaign Setting** (Updated 12-9-2019)
- Rat Queens: The Hangover

---

## File Layout on Disk

```
/mnt/fortress2/ttrpg/
├── extracted/pages/
│   ├── 5th Edition (5e)/          ← 506 markdown files
│   │   └── [title]__[author/path]__[subpath]__[filename].md
│   ├── Pathfinder 1e/             ← 1 file (PFRPG SRD)
│   └── SRD 5.2.1 (CC)/           ← 1 file (SRD_CC_v5.2.1)
├── manifest/
│   ├── CATALOG.md                 ← human-readable index
│   ├── catalog.json               ← full metadata
│   └── catalog.csv                ← spreadsheet format
├── projects/ttrpg-text-extract/
│   ├── book_types.yaml            ← classification taxonomy
│   └── corpus_filter.yaml         ← which books to process
└── ... (source PDFs, DB, configs)
```

File naming convention uses `__` as separator:
`<Edition>__[Category]__[Subcategory]__[Book Title]__[Page Type].md`

Categories include: Adventures, Supplements, Sourcebooks, Basic Rules, Setting, Characters/Sheets, DM ONLY, AL quests, etc.
