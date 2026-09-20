# DB examples — good / bad / mixed assembly (2026-07-24)

**Source:** Widow `news_intel`, live read-only queries.  
**Excluded (do not fix):** `politics` id **3775** — *Trump's Foreign Policy Backfires as Oil Prices Soar Amid Global Conflict Escalation* (123 members; operator’s example).

**Rebuild context:** Politics only **6** active storylines; finance **14**; legal **18**; medicine **5** (but max **276** members). True “good” bags are scarce; “better” means relatively tighter theme + usable summary, not perfect.

---

## BAD

### B1 — medicine / 3758 (kitchen-sink mega + hallucinated summary)

| Field | Value |
|-------|--------|
| Title | Medtronic's 780G Insulin Pump Shows Promise in Latino Patients, But Effectiveness of New Psoriasis Treatment Unclear |
| Members | **242** |
| avg relevance | **0.950** (all high) |
| relationship_type | **related × 242** (zero `core`) |
| On-theme titles | Medtronic/780G/insulin ≈ **0**; psoriasis ≈ **1** |
| analysis_summary | Narrates Medtronic 780G + psoriasis laser as if evidence exists |

**Sample member titles (all score 0.95):** Rademikibart IV for Acute Asthma…; First Attempt Success in Tracheal Intubation…; Avatar-Based Serious Game for Cardiac Rehab…; Clinical Feasibility Study of Upright Breast CT…; Fitbit-Tracked Micromovement…; Short Bowel Syndrome study; Peanut Skin Extract glucose; Corticosteroid Injection pulpitis; Distal Radius Casting; Knee Osteoarthritis Fetuin-A; ZEPU-AI3 Lower Limb Robot; AI-Assisted Cholecystectomy.

**Summary head:** claims studies show promise for 780G in Latino patients — **not reflected in membership titles**.

**Pattern:** Compound title + uniform high scores + all `related` → LLM invents title-shaped narrative from thin/wrong keepers. **chars_per_link ≈ 5.3**.

---

### B2 — medicine / 3750 (title vs members mismatch admitted)

| Field | Value |
|-------|--------|
| Title | Ongoing: Hotspot Stereotactic Ablative Radiotherapy Versus Traditional… |
| Members | **63** |
| On-theme (SABR/stereotactic/radiotherapy) | **2 / 63** |
| analysis | Explicitly: *“The articles provided do not seem to match the storyline title…”* |

**Off-theme samples:** Bowel Obstruction Post Appendectomy; Parkinson’s gene therapy; Post-TB pulmonary rehab; Zirconia crowns; Adolescent alcohol Path180; CIPN rehab; Vagus nerve stimulation…

**Pattern:** Shell/`Ongoing:` title + clinical-trial absorb soup; summary correctly complains but membership remains.

---

### B3 — legal / 3791 (108-member news dump)

| Field | Value |
|-------|--------|
| Title | Courts Split on Conviction Appeals as Daycare Head and Trump Adviser Face Different Outcomes |
| Members | **108** |
| avg relevance | 0.75 uniform |
| analysis_summary | **empty** |

**Random member titles:** Homelessness in LA…; Metal pole murder Boylston T; Nebraska gunowners parks…; Blue Line riders disgusted; Senate stopgap budget; Houthis attack Saudi tankers; Melania Trump sanctions Wolff; France heat-wave deaths; Pediatric nurse charged…; Italy jeweler who killed robbers; Ban Congress sleeping with staff; UK PM Burnham energy tax cut.

**Pattern:** Title is courtroom-specific; bag is general wire. No summary yet — pure membership failure.

---

### B4 — finance / 3790 (compound title, theme-less bag)

| Field | Value |
|-------|--------|
| Title | Malaysia's Formula One Return May Boost Shipping Industry as Japan Banks Merge |
| Members | **29** |
| analysis | empty |
| Members | Singapore FDI; Axiom HK IPO; LSE nonstop trading; India refiners/Russia oil; GAM on 24h trading; Shvets geopolitics; Chinese FDI India; Pakistan sukuk; EM currencies; Saudi crude Red Sea; Mauritius tax; Japan 40y yield… |

**Pattern:** Title concatenates three unrelated finance headlines; membership is a market wrap dump.

---

### B5 — finance / 3774 (summary admits mismatch)

| Field | Value |
|-------|--------|
| Title | Global Investors Flee Indian Bonds as Japan Insurers Take on Record Super-Long Debt |
| Members | **21**, avg_rel **0.350**, lo_rel **21** |
| analysis | *“The article does not directly relate to the storyline title. However…”* then invents a thread |

---

### B6 — politics / 3754 (stub after polluted members)

| Field | Value |
|-------|--------|
| Title | Trump's Foreign Policy Agenda Under Fire as Global Tensions Rise |
| Members | **29**, **all** lo_rel (avg **0.350**) |
| analysis | Title-focused stub: could not produce clean narrative; review membership |

(Sibling pattern to 3775; included as another politics bag, not to fix.)

---

## MIXED / RELATIVELY BETTER

### M1 — finance / 3762 (partial oil/Iran coherence)

| Field | Value |
|-------|--------|
| Title | Oil Rebound Triggers Record Bearish Bets on Kiwi Amid Iran Conflict and China Tax Crackdown |
| Members | **37** |
| Loose on-theme (oil/Iran/Kiwi/China/tax) | **19 / 37**; strict oil/Iran **6** |
| analysis_len | **2363** (~64 chars/link) — engages oil/Iran narrative |

**On-theme samples:** Hedge Funds Dial Up Bearish Kiwi Bets…; US Gasoline Tops $4… Iran War; Palm Climbs… Iran Conflict; Iran War Forces… LNG; Kuwait Dollar Bonds as Iran Strikes…

**Still off:** Cadillac IPO; China magnets; chipmakers wrap; Goldman tech sell; short bets AI risks…

**Why “mixed”:** Better than Medtronic (real thematic core exists) but still a multi-topic market bag with compound title.

---

### M2 — legal / 3776 (small N, weak theme purity)

| Field | Value |
|-------|--------|
| Title | Heller and Bruen gun laws here to stay after court rulings |
| Members | **4**, avg_rel 0.76, analysis_len 1171 |

**Members:** (1) Heller and Bruen are here to stay; (2) License plate data lawsuit California; (3) Teen drops Meta social-media addiction lawsuit; (4) AstraZeneca immune from Covid vaccine injury lawsuit.

**Why not “good”:** Only 1/4 is on-title; others are generic “lawsuit” glue. Small N + long summary ≠ precision.

---

## GOOD

**None confidently labeled “good” in this rebuild window.** Criteria used:

- Distinctive title tokens appear in ≥70% of member titles, **and**
- Summary does not disclaim mismatch / invent missing studies, **and**
- `n_links` not a domain-wide dump.

Closest candidates (M1) still fail ≥70% purity. Reviewer should treat absence of goods as signal: current attach precision may be too low to produce tight proteins after flush.

---

## Cross-cutting metrics

| Example | n_links | analysis_len | chars_per_link | Notes |
|---------|---------|--------------|----------------|-------|
| medicine/3758 | 242 | 1279 | 5.3 | Invented Medtronic narrative |
| legal/3791 | 108 | 0 | 0 | No summary |
| medicine/3750 | 63 | 834 | 13.2 | Summary admits mismatch |
| finance/3762 | 37 | 2363 | 63.9 | Best mixed |
| finance/3774 | 21 | 990 | 47.1 | Summary admits mismatch |
| legal/3776 | 4 | 1171 | 292.8 | Small but impure |

---

## Query notes for reproduction

Schemas: `politics`, `finance`, `legal`, `medicine`, `artificial_intelligence`.  
Join `storyline_articles` → `articles` on `article_id`.  
Filter `storylines.status = 'active'`.  
Theme purity: count member titles `ILIKE` distinctive tokens from storyline title.
