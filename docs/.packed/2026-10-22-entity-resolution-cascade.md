
---

## Normalization Deep-Dive

### `_normalize_name(name, entity_type)` — title/suffix stripping

| Input | Output |
|-------|--------|
| "President Joe Biden" | "Joe Biden" |
| "Dr. Jane Smith" | "Jane Smith" |  
| "Microsoft Inc." | "Microsoft" |
| "BlackRock Group Holdings" | "BlackRock" |

### `_normalize_for_fuzzy(text)` — canonical tokenization

```
Input:  "U.S. Department of State"
Step 1: "u.s. department of state"         (lowercase)
Step 2: "usa department of state"          (abbreviations)
Step 3: "usa department of state"          (non-alnum → space, collapse)
Step 4: "usa department of state"          (no typo to fix)
Output: "usa department of state"           (final stable key)
```

---

## Architecture Diagram

```
                   ┌──────────────────────────────┐
                   │     Input: raw entity name    │
                   └──────────────┬───────────────┘
                                  ▼
                    ┌─────────────────────────┐
  Step 1   │  title/suffix stripping          │
           │  (person titles, org suffixes)   │
                    └──────────────┬──────────┘
                                  ▼
                    ┌─────────────────────────┐
  Step 2   │  fuzzy normalization             │
           │  NFKC + abbrev + typo repair     │
                    └──────────────┬──────────┘
                                  ▼
              ┌─────────────────────────────┐
  Step 3   │ known equivalence bucket?      │
           │ YES → return bucket id (EQ)    │
           │ NO  → continue cascade         │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
  Step 4   │ last word surname check        │
           │ blocked by role word list?     │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
  Step 5   │ full surface form expansion    │
           │ (all forms that should match)  │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
  Step 6   │ DB lookup in entity_canonical  │
           │ via normalized key / bucket    │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
  Step 7   │ merge candidate detection      │
           │ (if no exact match)            │
              └──────────────┬──────────────┘
                             ▼
              ┌─────────────────────────────┐
  Step 8   │ cross-domain linking           │
           │ shared canonical across silos  │
              └─────────────────────────────┘
```

---

## Key Rules (Do Not Violate)

1. **Normalization is lossy.** Never use normalized tokens for display — they are comparison keys only.
2. **Equivalence buckets are frozen at import.** New aliases require a code change or DB-level alias injection; hot reload is not supported.
3. **Surname matching only applies when the last word is NOT in the role blocklist.** This prevents corporate titles from being treated as surnames.
4. **Fuzzy normalization handles Unicode, abbreviations, and typos.** Do not bypass it for "cleaner" matching — it produces the stable keys.

---

## Related Files

- `api/services/entity_resolution_service.py` — full cascade logic (this note's source)
- `api/services/quiver_entity_resolver.py` — external resolver integration
- `api/services/claim_extraction_service.py` — feeds entities into this pipeline
- `docs/RAG_ENHANCEMENT_ROADMAP.md` — T1.2 enhancement plans

# Entity Resolution Cascade — 8-Step Logic Chain

> **Operators:** This is the entity disambiguation and alias population pipeline that maps `(domain, entity_name, entity_type)` to `canonical_entity_id`.  
> Last reviewed: 2026-10-22 · Source: `api/services/entity_resolution_service.py`, `quiver_entity_resolver.py`.

---

## Why This Is Hard (From Code Alone)

Entity resolution in News Intelligence must handle the same real-world entity appearing across dozens of surface forms — "President Biden," "Joe Biden," "Biden, Joseph," "the President," etc. — and decide whether two mentions refer to the same canonical entity or different ones. The cascade is complex because **no single heuristic works for all cases**; it chains together normalization, abbreviation mapping, surname-only matching, fuzzy comparison, and equivalence bucket resolution.

---

## The 8-Step Cascade

### Step 1: Input Normalization

Strip titles and organizational suffixes before any comparison:

```python
# Titles stripped from person entities
TITLE_PREFIXES = re.compile(r"^(president|vice president|senator|rep\.|...)\s+")

# Org suffixes stripped for organization entities
ORG_SUFFIXES = re.compile(r"\s+(inc\.?|corp\.?|ltd\.?|llc|plc|...)$")
```

Result: "President Joe Biden" → "Joe Biden"; "Meta Inc." → "Meta".

### Step 2: Fuzzy Normalization (canonical form)

Aggressive token-level normalization producing a **stable comparison key** — not for display, only for matching:

1. Unicode NFKC decomposition + lowercase
2. Abbreviation expansion: `U.S.A.` → `usa`, `U.K.` → `uk`, `E.U.` → `eu`
3. Non-alphanumeric → spaces; collapse whitespace
4. Light typo repair: `iunited` → `united` (leading "iu" before vowel)
5. Duplicate letter collapsing

### Step 3: Known Equivalence Bucket Lookup

Pre-computed alias groups at import time, frozen into the running process:

```python
("United States", "USA", "U.S.", "the United States") → bucket:eq:0
("United Kingdom", "Great Britain", "UK", "Britain")  → bucket:eq:1
("European Union", "EU", "E.U.")                       → bucket:eq:2
("New York City", "NYC", "N.Y.C.")                     → bucket:eq:4
```

If the fuzzy-normalized key hits a known bucket, **all forms in that bucket are treated as identical** for SQL `= ANY(...)` lookups.

### Step 4: Surname-Only Matching (Last Word)

When comparing names, if the last word is not a role/title, it's treated as a surname:

```python
LAST_WORD_ROLE_BLOCKLIST = frozenset({
    "executives", "chair", "chairs", "director", 
    "spokesperson", "chief", "officer", ...
})
```

So "John Smith" can match "Smith, John" but "Microsoft executives" will **not** have "executives" treated as a surname.

### Step 5: Full Bucket Expansion for Overlap Checks

For any candidate name, compute all surface forms that should be checked against the DB:

```python
out = set()
out.add(name.lower())                           # raw lowered
out.add(normalized_name.lower())               # title/suffix stripped
out.add(fuzzy_normalized)                      # full fuzzy form
bid = equivalence_bucket_id(fuzzy_normalized)
if bid: out.update(BUCKET_TO_TERMS[bid])       # expand all known aliases
```

### Step 6: DB Lookup with Fuzzy Key

Query `entity_canonical` using the normalized key or equivalence bucket. The lookup checks `(domain, entity_type, normalized_name)` to find a match in the canonical table.

### Step 7: Merge Candidate Detection

When no exact match is found, identify potential merge candidates by comparing the full expanded surface forms against existing entries. Low-confidence matches flag entities for manual review or batch alias population.

### Step 8: Cross-Domain Entity Linking

Entities resolved in one domain (e.g., "Joe Biden" in politics) can be linked to related entities in other domains via shared canonical keys, enabling cross-domain intelligence aggregation.
