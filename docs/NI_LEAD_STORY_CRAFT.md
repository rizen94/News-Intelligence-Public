# NI lead story craft (AutoGen connection synthesis)

AutoGen connection synthesis is **lead generation**, not finished journalism. Investigators deepen; desk promotes. This note maps classic craft onto research → prune → narrative so leads answer **why should I care?** before they look “done.”

See also: [NEWS_INTELLIGENCE_INTEGRATION.md](NEWS_INTELLIGENCE_INTEGRATION.md) (three-modal cycle).

## Fact pack ≠ story

A collection of linked facts is a notebook. A **story** needs:

| Piece | Job |
|-------|-----|
| **Angle** | Lens: who gains/loses, what changed, what’s at stake |
| **Walkaway** | One sentence the reader leaves with (`walkaway:` in draft + `evidence_snapshot.json`) |
| **Nut graf** | Justifies the story — purpose, timeliness, stakes (`## Why this matters (nut graf)`) |

Without a nut graf, survivors are research notes, not a reason to keep reading.

## How readers follow news

1. **Lede** — who / what / when / where (the change or act)
2. **Nut graf** — why it matters / what’s at stake
3. **Body** — evidence (inverted pyramid or short trail that returns to the nut)
4. **Attribution** — named people/orgs **doing things**; quotes as reaction, not hubs

Readers follow **actors over time**, not “entity X appeared in N storylines.”

## News values (selection, not similarity)

Use as prune / close criteria:

- **Impact / consequence** — who is affected, how much
- **Conflict / negativity** — tension, dispute, failure, risk
- **Personification** — named humans or specific orgs as actors
- **Unexpectedness** — surprise vs ambient wallpaper
- **Proximity / meaningfulness** — relevance to the audience
- **Elite persons/orgs** — elite *actions* matter; elite *wallpaper* (ambient nouns) does not

Editorial kill questions: What’s the **change**? Who **did** what to whom? What’s the **consequence**? If I cut the bottom half, is there still a story?

## Mapping onto NI stages

| Stage | Journalism job |
|-------|----------------|
| **Research** | Gather trail hops (actor / role / claim), not hub co-occurrence |
| **Prune** | Editorial kill: drop source-tags, weak co-mention, no-stakes chains |
| **Narrative** | Lede + **required nut graf** + walkaway; thin leads rotate with `reason=thin_no_stakes` |

If stakes cannot be supported from survivors, the runner writes a **THIN** pack (`NARRATIVE: THIN` / `thin_no_stakes`) so the session still rotates without pretending the lead is strong.

## arXiv is a source tag, not a story actor

**arXiv** (and `arXiv.org` / `arxiv …` aliases) is preprint **venue / publisher metadata**. It must never be:

- a hop bridge entity
- a prune survivor
- a seed enqueue reason
- a narrative “connection” hub

Implementation: `api/shared/hub_denylist.py` (NI port of Homelab craft) (denylist) wired into hops, prune, and `survivor_candidate_seed_ids`. Broader mega-hub wallpaper (Google / NVIDIA as ambient nouns, “Large Language Models”, etc.) is a **later** pass — do not confuse elite *actors* with venue wallpaper.

## Kernel → trail → nut (target shape)

1. Start from a **kernel** (claim, act, filing, quote) — not top-N entity counts  
2. Follow **one spine actor** (person → employer → counterparty → reaction)  
3. Stop when you can write a nut graf; do not keep absorbing co-mentions  
4. If you cannot write “X matters because Y,” it is not a lead yet  

Full spine-trail SQL is deferred; this craft gate + arXiv ban comes first.
