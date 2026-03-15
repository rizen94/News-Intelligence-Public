# Editorial Display Strategy: From Intelligence to Interface

> **Purpose:** Design reference for presenting intelligence to readers. Use for Dashboard, Briefings, Report, and any editorial-style UI.  
> **Principle:** Readers scan before they read. Create an instant visual hierarchy; support progressive disclosure from glance → scan → read → dive.

---

## 1. The Hierarchy of Attention

The most critical insight: **readers scan before they read**. The display must create an instant visual hierarchy that communicates importance without requiring thought.

```
Primary Scan Pattern (2-3 seconds):
┌─────────────────────────────────────┐
│ DOMINANT HEADLINE                   │ ← 70% will read
│ [Visual weight: massive]            │
├─────────────────────────────────────┤
│ Secondary lead | Third lead         │ ← 40% will scan
│ [Medium weight] | [Medium weight]   │
├─────────────────────────────────────┤
│ Supporting stories in digest format │ ← 20% will browse
│ [Lightweight, scannable]            │
└─────────────────────────────────────┘
```

---

## 2. The Intelligence Density Problem

Rich intelligence, limited cognitive bandwidth. Use **progressive disclosure**:

| Layer | Question | Content |
|-------|----------|--------|
| **Layer 1: The Glance** | What happened? | Single-sentence headline; one number/fact; story phase (Breaking/Developing/Analysis) |
| **Layer 2: The Scan** | Why should I care? | 2–3 bullet developments; perspective indicators; impact preview (markets ↓, policy likely) |
| **Layer 3: The Read** | Tell me more | Full narrative; context sidebar; timeline; multiple perspectives |
| **Layer 4: The Dive** | I need everything | Links to Investigate; raw intelligence; source documents |

---

## 3. Visual Grammar for Intelligence

| Type | Treatment |
|------|-----------|
| **Breaking** | Red accent/pulse; present tense; timestamp prominent ("12 min ago"); what's new highlighted |
| **Investigations/Tracking** | Progress/phase indicators; status changes; connection lines; "What we're watching for" callout |
| **Analysis/Synthesis** | Quieter, spacious; pull quotes; key insight boxes; takeaway summaries |
| **Cross-Domain** | Visual bridges; shared entity highlighting; "See also" with relevance |

---

## 4. The Newspaper Metaphor, Reimagined

| Traditional | Modern equivalent |
|-------------|-------------------|
| Above/below the fold | Above/below the scroll |
| Column width | Card width and text measure |
| Jump lines | Progressive disclosure (expand in place) |
| Sections | Domain switching (politics / finance / science-tech) |
| Edition times | Time-based layouts (morning / midday / evening) |

**Leverage:** Personalization, real-time updates with change highlighting, infinite depth via disclosure, interactive timelines, live sentiment/impact.

---

## 5. Information Architecture by Time

- **Morning (6–9 AM):** Overnight developments; "While you were sleeping"; day-ahead preview; coffee-friendly, mobile-first.
- **Midday (11–14):** Breaking priority; quick scan; 5-minute reads; market updates.
- **Evening (17–20):** Analysis and context; "What it means"; tomorrow's watch; longer reads.
- **Weekend:** Magazine depth; week in review; pattern analysis; investigation deep dives.

---

## 6. Cognitive Load Balance

- **Reduce fatigue:** ≤3 leads; clear must-read / should-read / could-read; consistent placement; predictable interactions.
- **Aid comprehension:** Headlines that stand alone; numbers sparing but specific; show change/direction visually; obvious grouping.
- **Enable flow:** Smooth scroll; no jarring transitions; consistent rhythm; clear end points.

---

## 7. Mobile-First Information Design

- **Thumb zone:** Critical actions in reach; swipe for more/less; tap to expand; long-press for context.
- **Scroll story:** Each viewport height = one complete thought; natural breaks; sticky headers; progress indicators.
- **Attention budget:** Assume 30-second sessions; front-load value; every pixel counts; no decoration.

---

## 8. Trust and Authority Signals

- **Attribution:** Multi-source (3+), confidence levels, freshness, correction/update flags.
- **Quality:** Verification badges, exclusive/expert markers, impact tracking.
- **Transparency:** "Why this is the lead"; coverage gaps; perspective balance; collapsible methodology.

---

## 9. Ambient Intelligence Layer

- **Peripheral:** Status bar alerts; edge indicators; subtle animation for new; optional audio for breaking.
- **Environment:** Dark mode; reduced motion; text size; reading-speed adaptation.

---

## 10. Success Metrics and Display

- **Relevance:** Subtle “getting better at what matters to you” signal.
- **Coverage:** Comprehensiveness; perspective balance; source diversity.
- **Impact:** “This story led to…” follow-ups; prediction accuracy; real-world outcome links.

---

## Key Principles Summary

1. **Respect the scan** — Most users won’t read deeply.
2. **Progressive disclosure** — Details on demand, not by default.
3. **Visual hierarchy is survival** — Without it, nothing gets read.
4. **Time-aware layouts** — Morning rush vs evening analysis.
5. **Mobile thumb-first** — One-handed use.
6. **Trust through transparency** — Show your work when asked.
7. **Ambient awareness** — Support peripheral monitoring.
8. **Measure to improve** — Display adapts to usage.

**Goal:** Reader understands *what matters* in 30 seconds, *why it matters* in 2 minutes, and has *everything to go deep* in 10 minutes. The interface should feel inevitable.

---

## Where This Applies in News Intelligence

| Area | Apply |
|------|--------|
| **Dashboard** | Dominant lead + 2 secondary; story phase chips; time-based sections; links to Investigate. |
| **Briefings** | Glance (headline + phase) → Scan (bullets) → Read (synthesis) → Dive (event/storyline links). |
| **Report / Editorial** | Above-the-scroll lead; digest cards; progressive expand; trust signals (sources, freshness). |
| **Today's Report** (`/:domain/report`) | **Primary implementation** of this strategy: hierarchy (dominant → 2 secondary → digest), time-of-day layout (morning/midday/evening/weekend), trust signals (freshness, source count, "Why this is the lead"), visual grammar (Breaking/Developing/Analysis), progressive disclosure (glance → scan → read → dive). |
| **Investigate** | Phase/progress for events; “what we’re watching”; connection lines; link to narrative threads. |
| **Finance / Commodity** | Impact preview; numbers + direction; cross-domain “see also.” |
| **New “Daily Brief” or “Editorial” view** | Build from this doc: hierarchy, time layout, trust, mobile-first. |

See also: [WEB_PRODUCT_DISPLAY_PLAN.md](WEB_PRODUCT_DISPLAY_PLAN.md), [NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md](NEWSPAPER_EDITORIAL_PRODUCT_STRATEGY.md), [PROJECT_CAPABILITIES_BRIEF.md](PROJECT_CAPABILITIES_BRIEF.md).
