#!/usr/bin/env python3
"""Seed neurodiversity research vault notes from DB + web/wiki basics.

1. Ensure subject entities (Autism, ADHD, AuDHD, Neurodiversity)
2. Enrich ``50_Science/40_Topics/*.md`` with Wikipedia, CDC/NIMH basics,
   and published knowledge-profile assertions from the research pathway
3. Write clippings for profiled research papers (done status)
4. Optionally preseed top neurodiversity entities from mentions
5. Sync tags/links into Postgres

Usage::

  set -a && source .env && set +a
  export NEWS_INTEL_VAULT_PATH=/mnt/news-intelligence-vault
  export NEWS_INTEL_VAULT_WRITE=true NI_VAULT_NOTES_ENABLED=true
  PYTHONPATH=api uv run python api/scripts/seed_neurodiversity_research_vault.py
  PYTHONPATH=api uv run python api/scripts/seed_neurodiversity_research_vault.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PROJECT_ROOT = os.path.abspath(os.path.join(_API_ROOT, ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(Path(_API_ROOT) / ".env", override=False)
    load_dotenv(Path(_PROJECT_ROOT) / ".env", override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD"):
    pw = Path(_PROJECT_ROOT) / ".db_password_widow"
    if pw.is_file():
        os.environ["DB_PASSWORD"] = pw.read_text().strip()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_neurodiversity_research_vault")

DOMAIN = "neurodiversity"

# Standing boards + wiki/web lookup queries
SUBJECTS: dict[str, dict[str, Any]] = {
    "Autism": {
        "wiki_queries": ["Autism", "Autism spectrum disorder"],
        "web_basics": [
            {
                "title": "CDC — Clinical testing and diagnosis for ASD",
                "url": "https://www.cdc.gov/autism/hcp/diagnosis/index.html",
                "bullets": [
                    "DSM-5 ASD requires persistent social-communication deficits across contexts plus ≥2 restricted/repetitive behavior patterns; symptoms in early development with functional impairment.",
                    "Diagnosis draws on caregiver developmental history and clinician observation; earlier evaluation enables earlier supports.",
                ],
            },
            {
                "title": "NIMH — Autism Spectrum Disorder",
                "url": "https://www.nimh.nih.gov/health/publications/autism-spectrum-disorder",
                "bullets": [
                    "ASD is a neurodevelopmental condition affecting social interaction, communication, learning, and behavior; signs often appear in the first two years of life.",
                    "Adult diagnosis is harder because symptoms can overlap with anxiety or ADHD; referral to clinicians experienced with ASD is recommended.",
                ],
            },
        ],
    },
    "ADHD": {
        "wiki_queries": [
            "Attention deficit hyperactivity disorder",
            "ADHD",
        ],
        "web_basics": [
            {
                "title": "NIMH — ADHD",
                "url": "https://www.nimh.nih.gov/health/topics/attention-deficit-hyperactivity-disorder-adhd",
                "bullets": [
                    "ADHD involves persistent inattention, hyperactivity, and/or impulsivity beginning in childhood (before age 12), present in ≥2 settings, impairing function.",
                    "Presentations: predominantly inattentive, predominantly hyperactive-impulsive, or combined; symptoms can shift across the lifespan.",
                ],
            },
            {
                "title": "NIMH — ADHD: What You Need to Know",
                "url": "https://www.nimh.nih.gov/health/publications/attention-deficit-hyperactivity-disorder/index.shtml",
                "bullets": [
                    "Children ≤16 need ≥6 symptoms in a domain; adults/youth >16 need ≥5; symptoms ≥6 months and not better explained by another condition.",
                    "Evaluation often uses rating scales plus cognitive/executive-function testing to identify strengths, challenges, and comorbidity.",
                ],
            },
        ],
    },
    "AuDHD": {
        "wiki_queries": [
            "Attention deficit hyperactivity disorder",
            "Autism spectrum disorder",
        ],
        "web_basics": [
            {
                "title": "Expert consensus — ADHD + ASD identification/treatment (BMC Medicine)",
                "url": "https://link.springer.com/article/10.1186/s12916-020-01585-y",
                "bullets": [
                    "DSM-5 removed ASD as an exclusion for ADHD — co-occurrence is recognized and both should be assessed when indicated.",
                    "ADHD 'presentations' (vs fixed subtypes) reflect that symptom profiles can change over development; comorbid ASD needs explicit note in care planning.",
                ],
            },
        ],
    },
    "Neurodiversity": {
        "wiki_queries": ["Neurodiversity", "Neurodivergence"],
        "web_basics": [
            {
                "title": "Wikipedia — Neurodiversity (paradigm overview)",
                "url": "https://en.wikipedia.org/wiki/Neurodiversity",
                "bullets": [
                    "Neurodiversity frames variation in sensory processing, cognition, social comfort, and focus as natural neurobiological diversity rather than solely as pathology.",
                    "Clinical diagnosis (ASD, ADHD, etc.) and the neurodiversity paradigm can coexist: one describes functional criteria/supports; the other frames identity and societal design.",
                ],
            },
        ],
    },
}

# Current clinical SSOT = DSM-5-TR (2022). Older editions kept as historic context.
# Summaries are paraphrased from APA/CDC/NIMH public criteria pages — not verbatim DSM text.
DSM_CURRENT = {
    "edition": "DSM-5-TR (2022)",
    "note": (
        "Use DSM-5-TR as the current clinical reference. DSM-5 (2013) criteria are "
        "largely continuous; DSM-5-TR clarified ASD Criterion A to require **all** "
        "three social-communication domains."
    ),
    "sources": [
        {
            "title": "APA — DSM-5-TR Autism Spectrum Disorder criterion A clarification",
            "url": "https://www.psychiatry.org/File%20Library/Psychiatrists/Practice/DSM/DSM-5-TR/APA-DSM5TR-AutismSpectrumDisorder.pdf",
        },
        {
            "title": "CDC — DSM-5 ASD diagnostic criteria (public summary)",
            "url": "https://www.cdc.gov/autism/hcp/diagnosis/index.html",
        },
        {
            "title": "APA — Highlights of changes from DSM-IV-TR to DSM-5",
            "url": "https://www.psychiatry.org/File%20Library/Psychiatrists/Practice/DSM/APA_DSM_Changes_from_DSM-IV-TR_-to_DSM-5.pdf",
        },
        {
            "title": "Autism Speaks — DSM-5 and autism FAQ (historic labels)",
            "url": "https://www.autismspeaks.org/dsm-5-and-autism-frequently-asked-questions",
        },
        {
            "title": "NIMH — ADHD (current clinical overview)",
            "url": "https://www.nimh.nih.gov/health/topics/attention-deficit-hyperactivity-disorder-adhd",
        },
        {
            "title": "PMC — ADHD historical neuropsychological perspective (DSM-III→5)",
            "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC5724393/",
        },
    ],
}

DSM_BY_SUBJECT: dict[str, dict[str, Any]] = {
    "Autism": {
        "current_label": "Autism Spectrum Disorder (ASD)",
        "current_criteria": [
            "**A (DSM-5-TR):** Persistent deficits in social communication **and** social interaction across multiple contexts, as manifested by **all** of: (1) social-emotional reciprocity; (2) nonverbal communicative behaviors for social interaction; (3) developing/maintaining/understanding relationships.",
            "**B:** Restricted, repetitive patterns of behavior, interests, or activities — **≥2** of: stereotyped/repetitive movements or speech; insistence on sameness/routines; highly restricted fixated interests; hyper-/hyporeactivity to sensory input.",
            "**C–E:** Symptoms present in the early developmental period (may not fully manifest until social demands exceed capacity); cause clinically significant impairment; not better explained by intellectual developmental disorder or global developmental delay alone.",
            "**Specifiers:** severity Levels 1–3 (support needs); with/without intellectual impairment; with/without language impairment; associated medical/genetic/environmental factor; associated other neurodevelopmental/mental/behavioral disorder; with catatonia.",
        ],
        "historic": [
            {
                "edition": "DSM-IV / DSM-IV-TR (1994/2000)",
                "labels": [
                    "Autistic Disorder",
                    "Asperger's Disorder",
                    "Childhood Disintegrative Disorder",
                    "PDD-NOS",
                ],
                "bullets": [
                    "Pervasive Developmental Disorders were split into separate named diagnoses rather than one spectrum.",
                    "Asperger's Disorder: social impairment + restricted/repetitive behaviors **without** clinically significant general language delay (and typically without intellectual disability).",
                    "PDD-NOS: clinically significant social/communication atypicality not meeting full Autistic Disorder or Asperger's criteria.",
                    "DSM-5 transition rule: well-established DSM-IV Autistic Disorder / Asperger's / PDD-NOS → give ASD (do not strip identity labels from records).",
                ],
            },
            {
                "edition": "DSM-III / DSM-III-R (1980/1987)",
                "labels": ["Infantile Autism", "Autistic Disorder", "PDD"],
                "bullets": [
                    "DSM-III introduced Infantile Autism as a distinct diagnosis (onset before 30 months in early formulations).",
                    "DSM-III-R broadened Autistic Disorder criteria and kept PDD as the umbrella framing later refined in DSM-IV.",
                ],
            },
            {
                "edition": "DSM-5 (2013) → DSM-5-TR (2022)",
                "labels": ["Autism Spectrum Disorder", "Social (Pragmatic) Communication Disorder"],
                "bullets": [
                    "Four DSM-IV PDD categories collapsed into one ASD diagnosis with two symptom domains.",
                    "New Social (Pragmatic) Communication Disorder for social-communication deficits **without** restricted/repetitive behaviors.",
                    "DSM-5-TR Criterion A wording clarified to require **all three** social-communication subdomains (not any one).",
                ],
            },
        ],
        "related_historic_notes": [
            "Asperger's Disorder",
            "PDD-NOS",
            "Autistic Disorder",
            "Social Communication Disorder",
        ],
    },
    "ADHD": {
        "current_label": "Attention-Deficit/Hyperactivity Disorder (ADHD)",
        "current_criteria": [
            "**A:** Persistent pattern of inattention and/or hyperactivity-impulsivity that interferes with functioning or development, with ≥6 symptoms in a domain for children (≤16) or ≥5 for age 17+ , lasting ≥6 months, inconsistent with developmental level.",
            "**Presentations (not fixed lifelong subtypes):** Combined; Predominantly inattentive; Predominantly hyperactive/impulsive. Specifiers also include partial remission and severity (mild/moderate/severe).",
            "**B–D:** Several symptoms present before age **12**; several symptoms in **≥2** settings; clear evidence of interference with social, academic, or occupational functioning.",
            "**E:** Symptoms not solely explained by another mental disorder (psychosis, mood, anxiety, personality, substance, etc.).",
            "**Comorbidity change vs DSM-IV:** ASD is **no longer** an exclusion — ADHD + ASD may be diagnosed together when both criteria are met.",
        ],
        "historic": [
            {
                "edition": "DSM-II (1968)",
                "labels": ["Hyperkinetic Reaction of Childhood"],
                "bullets": [
                    "Early DSM framing emphasized overactivity/restlessness more than attention as the core construct.",
                ],
            },
            {
                "edition": "DSM-III (1980)",
                "labels": [
                    "Attention Deficit Disorder (ADD) with Hyperactivity",
                    "Attention Deficit Disorder (ADD) without Hyperactivity",
                ],
                "bullets": [
                    "Renamed from hyperkinetic framing to **Attention Deficit Disorder**, centering attention.",
                    "Explicit **ADD without Hyperactivity** subtype — the historical root of the colloquial label \"ADD\".",
                ],
            },
            {
                "edition": "DSM-III-R (1987)",
                "labels": ["Attention-Deficit Hyperactivity Disorder", "Undifferentiated ADHD"],
                "bullets": [
                    "Renamed to ADHD; dropped dual ADD subtypes in favor of a single ADHD construct.",
                    "Undifferentiated ADHD used for presentations without prominent hyperactivity (bridge from ADD/WO).",
                ],
            },
            {
                "edition": "DSM-IV / DSM-IV-TR (1994/2000)",
                "labels": [
                    "ADHD Combined Type",
                    "ADHD Predominantly Inattentive Type",
                    "ADHD Predominantly Hyperactive-Impulsive Type",
                    "ADHD NOS",
                ],
                "bullets": [
                    "Restored dimensional subtypes using 18 symptoms (9 inattentive / 9 hyperactive-impulsive).",
                    "Onset criterion: impairment before age **7** (later relaxed in DSM-5).",
                    "ASD/autism was generally treated as an exclusion for ADHD diagnosis.",
                ],
            },
            {
                "edition": "DSM-5 / DSM-5-TR (2013/2022)",
                "labels": ["ADHD (presentations)", "Other Specified / Unspecified ADHD"],
                "bullets": [
                    "Subtypes → **presentations** (profiles can change over the lifespan).",
                    "Onset moved to before age **12**; adult threshold reduced to 5 symptoms; cross-situational requirement strengthened.",
                    "Moved into Neurodevelopmental Disorders chapter; comorbidity with ASD allowed.",
                ],
            },
        ],
        "related_historic_notes": [
            "Attention Deficit Disorder (ADD)",
            "Hyperkinetic Reaction of Childhood",
            "ADHD Predominantly Inattentive Type",
        ],
    },
    "AuDHD": {
        "current_label": "Co-occurring ASD + ADHD (informal: AuDHD)",
        "current_criteria": [
            "Not a standalone DSM code — clinical practice under DSM-5/DSM-5-TR is to diagnose **both** ASD and ADHD when each set of criteria is independently met.",
            "DSM-IV generally excluded ADHD when PDD/autism was present; DSM-5 removed that exclusion — a major reason co-occurrence recognition rose after 2013.",
            "Differential caution: social disengagement/indifference to cues in ASD vs impulsivity/peer rejection patterns more typical of ADHD; both can present with inattention and emotional dysregulation.",
        ],
        "historic": [
            {
                "edition": "Pre–DSM-5",
                "labels": ["ASD/PDD with secondary attention problems (often not dual-coded)"],
                "bullets": [
                    "Many autistic people with attention/impulsivity needs were not formally dual-diagnosed because of the ADHD exclusion rule.",
                ],
            },
            {
                "edition": "DSM-5 / DSM-5-TR",
                "labels": ["ASD + ADHD (dual diagnosis)", "AuDHD (community/clinical shorthand)"],
                "bullets": [
                    "Dual coding is valid; care plans should address both social-communication/RRB supports and ADHD-related executive-function/attention supports.",
                ],
            },
        ],
        "related_historic_notes": ["Asperger's Disorder", "Attention Deficit Disorder (ADD)"],
    },
    "Neurodiversity": {
        "current_label": "Neurodiversity (paradigm; not a DSM diagnosis)",
        "current_criteria": [
            "Neurodiversity is **not** a DSM disorder category — it is a framework for understanding neurological variation (including people who do or do not meet clinical criteria).",
            "Clinical SSOT for specific conditions remains DSM-5-TR (ASD, ADHD, etc.) / ICD-11 when coding for care, education, and research.",
            "Useful bridge: DSM labels describe functional impairment thresholds; neurodiversity language describes identity, access, and environmental fit.",
        ],
        "historic": [
            {
                "edition": "Context across DSM eras",
                "labels": ["See ASD / ADHD historic notes"],
                "bullets": [
                    "Older labels (Asperger's, ADD, PDD-NOS, hyperkinetic reaction) still appear in records, self-identification, and longitudinal research cohorts — map them to current DSM-5-TR constructs without erasing historic meaning.",
                ],
            },
        ],
        "related_historic_notes": [
            "Asperger's Disorder",
            "Attention Deficit Disorder (ADD)",
            "PDD-NOS",
        ],
    },
}

# Historic label stubs under 50_Science/40_Topics/ (context notes, not living boards)
HISTORIC_DSM_NOTES: list[dict[str, Any]] = [
    {
        "title": "Asperger's Disorder",
        "slug_hint": "aspergers_disorder",
        "era": "DSM-IV / DSM-IV-TR",
        "maps_to": ["Autism"],
        "summary": (
            "DSM-IV diagnosis within Pervasive Developmental Disorders: social impairment and "
            "restricted/repetitive behaviors without clinically significant general language delay. "
            "Removed as a separate code in DSM-5; well-established diagnoses map to Autism Spectrum Disorder. "
            "Many people retain Asperger's as an identity/record label alongside ASD coding."
        ),
        "bullets": [
            "DSM-5 rule: established Asperger's → diagnose ASD (do not reclassify to Social Communication Disorder retroactively).",
            "Related current note: [[Autism]].",
        ],
        "sources": [
            "https://www.autismspeaks.org/dsm-5-and-autism-frequently-asked-questions",
            "https://www.psychiatry.org/File%20Library/Psychiatrists/Practice/DSM/APA_DSM_Changes_from_DSM-IV-TR_-to_DSM-5.pdf",
        ],
    },
    {
        "title": "PDD-NOS",
        "slug_hint": "pdd_nos",
        "era": "DSM-IV / DSM-IV-TR",
        "maps_to": ["Autism"],
        "summary": (
            "Pervasive Developmental Disorder Not Otherwise Specified — clinically significant "
            "social/communication atypicality that did not meet full Autistic Disorder or Asperger's criteria. "
            "Folded into Autism Spectrum Disorder in DSM-5; some borderline new cases may instead meet "
            "Social (Pragmatic) Communication Disorder if restricted/repetitive behaviors are absent."
        ),
        "bullets": [
            "Transition: established PDD-NOS → ASD under DSM-5 guidance.",
            "Related: [[Autism]], [[Social Communication Disorder]].",
        ],
        "sources": [
            "https://www.autismspeaks.org/dsm-5-and-autism-frequently-asked-questions",
        ],
    },
    {
        "title": "Autistic Disorder",
        "slug_hint": "autistic_disorder",
        "era": "DSM-III-R / DSM-IV",
        "maps_to": ["Autism"],
        "summary": (
            "Classic 'autism' diagnosis under DSM-III-R/DSM-IV within the PDD umbrella, typically "
            "with earlier/more pervasive language and developmental impacts than Asperger's. "
            "Superseded by Autism Spectrum Disorder in DSM-5."
        ),
        "bullets": [
            "Related current note: [[Autism]].",
        ],
        "sources": [
            "https://www.cdc.gov/autism/hcp/diagnosis/index.html",
        ],
    },
    {
        "title": "Social Communication Disorder",
        "slug_hint": "social_communication_disorder",
        "era": "DSM-5 / DSM-5-TR",
        "maps_to": ["Autism"],
        "summary": (
            "DSM-5 communication disorder for persistent deficits in the social use of verbal and "
            "nonverbal communication **without** the restricted/repetitive behaviors required for ASD. "
            "Not a retroactive replacement for Asperger's or PDD-NOS."
        ),
        "bullets": [
            "If RRBs are present with social-communication deficits, consider ASD instead.",
            "Related: [[Autism]].",
        ],
        "sources": [
            "https://www.autismspeaks.org/dsm-5-and-autism-frequently-asked-questions",
            "https://www.psychiatry.org/File%20Library/Psychiatrists/Practice/DSM/APA_DSM_Changes_from_DSM-IV-TR_-to_DSM-5.pdf",
        ],
    },
    {
        "title": "Attention Deficit Disorder (ADD)",
        "slug_hint": "attention_deficit_disorder_add",
        "era": "DSM-III (1980)",
        "maps_to": ["ADHD"],
        "summary": (
            "DSM-III name for what is now ADHD, including **ADD with Hyperactivity** and "
            "**ADD without Hyperactivity**. The without-hyperactivity subtype is the historical "
            "basis for the still-common colloquial term \"ADD\". Later manuals used ADHD "
            "(DSM-III-R+) and restored inattentive presentations under ADHD (DSM-IV/5)."
        ),
        "bullets": [
            "Rough modern mapping: ADD without Hyperactivity ≈ ADHD predominantly inattentive presentation.",
            "Related current note: [[ADHD]].",
        ],
        "sources": [
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC5724393/",
            "https://www.pbs.org/wgbh/pages/frontline/shows/medicating/adhd/diagnostic.html",
        ],
    },
    {
        "title": "Hyperkinetic Reaction of Childhood",
        "slug_hint": "hyperkinetic_reaction_of_childhood",
        "era": "DSM-II (1968)",
        "maps_to": ["ADHD"],
        "summary": (
            "DSM-II childhood diagnosis emphasizing overactivity, restlessness, and distractibility — "
            "a precursor construct later reconceptualized as Attention Deficit Disorder (DSM-III) "
            "and ADHD (DSM-III-R onward)."
        ),
        "bullets": [
            "Related current note: [[ADHD]].",
        ],
        "sources": [
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC5724393/",
        ],
    },
    {
        "title": "ADHD Predominantly Inattentive Type",
        "slug_hint": "adhd_predominantly_inattentive_type",
        "era": "DSM-IV subtype → DSM-5 presentation",
        "maps_to": ["ADHD"],
        "summary": (
            "DSM-IV subtype (≥6 inattentive symptoms, fewer than 6 hyperactive-impulsive). "
            "In DSM-5/DSM-5-TR this is a **presentation** specifier rather than a fixed subtype, "
            "acknowledging that profiles can shift with age. Often what people mean by \"ADD\"."
        ),
        "bullets": [
            "Related: [[ADHD]], [[Attention Deficit Disorder (ADD)]].",
        ],
        "sources": [
            "https://www.psychiatry.org/File%20Library/Psychiatrists/Practice/DSM/APA_DSM_Changes_from_DSM-IV-TR_-to_DSM-5.pdf",
            "https://www.nimh.nih.gov/health/publications/attention-deficit-hyperactivity-disorder/index.shtml",
        ],
    },
]

_KP_SECTION_RE = re.compile(
    r"\n## What we know \(NI research board\)\n(?:.*?)(?=\n## |\Z)",
    re.S,
)
_WEB_SECTION_RE = re.compile(
    r"\n## Reference basics \(web\)\n(?:.*?)(?=\n## |\Z)",
    re.S,
)
_DSM_SECTION_RE = re.compile(
    r"\n## DSM definitions \(clinical\)\n(?:.*?)(?=\n## |\Z)",
    re.S,
)
_CORPUS_SECTION_RE = re.compile(
    r"\n## Corpus papers \(seeded\)\n(?:.*?)(?=\n## |\Z)",
    re.S,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_subjects() -> dict[str, int]:
    from services.entity_resolution_service import resolve_to_canonical

    out: dict[str, int] = {}
    for name in SUBJECTS:
        eid = resolve_to_canonical(
            DOMAIN, name, "subject", create_if_missing=True
        )
        if eid is None:
            raise RuntimeError(f"could not resolve subject entity: {name}")
        out[name] = int(eid)
        logger.info("subject %s → entity_id=%s", name, eid)
    return out


def _load_knowledge_profile(title: str) -> dict[str, Any] | None:
    from services.knowledge_profile_service import list_profiles

    for p in list_profiles(domain_key=DOMAIN, status=None, limit=50):
        if (p.get("title") or "").strip().lower() == title.lower():
            return p
    return None


def _assertion_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(
            item.get("text")
            or item.get("assertion")
            or item.get("claim")
            or item.get("question")
            or ""
        ).strip()
    return str(item or "").strip()


def _build_kp_section(profile: dict[str, Any] | None) -> str:
    lines = [
        "## What we know (NI research board)",
        "",
        f"_Synced {_now_iso()[:19]}Z from published ``knowledge_profiles`` "
        f"(appraisal → auto-merge). Not news headlines._",
        "",
    ]
    if not profile:
        lines.append("_No published knowledge profile yet for this subject._")
        lines.append("")
        return "\n".join(lines)

    is_a = profile.get("is_assertions") or []
    not_a = profile.get("is_not_assertions") or []
    open_q = profile.get("open_questions") or []

    lines.append("### Supported")
    lines.append("")
    if is_a:
        for a in is_a[:12]:
            t = _assertion_text(a)
            if t:
                lines.append(f"- {t}")
    else:
        lines.append("- _None yet._")
    lines.append("")
    lines.append("### Not supported / contradicted")
    lines.append("")
    if not_a:
        for a in not_a[:8]:
            t = _assertion_text(a)
            if t:
                lines.append(f"- {t}")
    else:
        lines.append("- _None yet._")
    lines.append("")
    lines.append("### Open questions")
    lines.append("")
    if open_q:
        for a in open_q[:12]:
            t = _assertion_text(a)
            if t:
                lines.append(f"- {t}")
    else:
        lines.append("- _None yet._")
    lines.append("")
    return "\n".join(lines)


def _build_web_section(title: str) -> str:
    cfg = SUBJECTS[title]
    lines = [
        "## Reference basics (web)",
        "",
        f"_Curated {_now_iso()[:19]}Z from CDC / NIMH / peer-reviewed consensus. "
        f"Background framing only — NI board assertions remain evidence-gated._",
        "",
    ]
    for src in cfg.get("web_basics") or []:
        lines.append(f"### [{src['title']}]({src['url']})")
        lines.append("")
        for b in src.get("bullets") or []:
            lines.append(f"- {b}")
        lines.append("")
    return "\n".join(lines)


def _build_dsm_section(title: str) -> str:
    block = DSM_BY_SUBJECT.get(title) or {}
    lines = [
        "## DSM definitions (clinical)",
        "",
        f"_Current clinical SSOT: **{DSM_CURRENT['edition']}**. "
        f"Older editions are retained below for historic labels (Asperger's, ADD, PDD-NOS, etc.). "
        f"Paraphrased public criteria — not a substitute for the APA manual. "
        f"Synced {_now_iso()[:19]}Z._",
        "",
        f"> {DSM_CURRENT['note']}",
        "",
        f"### Current — {block.get('current_label') or title}",
        "",
    ]
    for c in block.get("current_criteria") or []:
        lines.append(f"- {c}")
    lines.append("")
    lines.append("### Historic editions / retired labels")
    lines.append("")
    for era in block.get("historic") or []:
        labels = ", ".join(f"**{x}**" for x in (era.get("labels") or []))
        lines.append(f"#### {era.get('edition')}")
        lines.append("")
        if labels:
            lines.append(f"- Labels: {labels}")
        for b in era.get("bullets") or []:
            lines.append(f"- {b}")
        lines.append("")
    related = block.get("related_historic_notes") or []
    if related:
        lines.append("### Historic vault notes")
        lines.append("")
        lines.append(", ".join(f"[[{n}]]" for n in related))
        lines.append("")
    lines.append("### Sources")
    lines.append("")
    for src in DSM_CURRENT.get("sources") or []:
        lines.append(f"- [{src['title']}]({src['url']})")
    lines.append("")
    return "\n".join(lines)


def _historic_object_id(key: str) -> int:
    """Stable synthetic object_id for historic DSM label notes (92xxxxxx)."""
    import hashlib

    digest = hashlib.md5(f"dsm-historic:{key}".encode("utf-8")).hexdigest()
    return 92_000_000 + (int(digest[:8], 16) % 1_000_000)


def _write_historic_dsm_notes(*, dry_run: bool) -> list[dict[str, Any]]:
    """Write/refresh historic DSM label notes under 50_Science/40_Topics/."""
    from services.vault_bridge_service import vault_root
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.database.connection import get_db_connection_context
    from shared.vault_note_contract import slugify_entity_name

    out: list[dict[str, Any]] = []
    root = vault_root()
    for note in HISTORIC_DSM_NOTES:
        title = note["title"]
        slug = slugify_entity_name(note.get("slug_hint") or title, max_len=60)
        rel = f"50_Science/40_Topics/{slug}.md"
        maps = ", ".join(f"[[{m}]]" for m in (note.get("maps_to") or []))
        sources = "\n".join(f"- {u}" for u in (note.get("sources") or []))
        bullets = "\n".join(f"- {b}" for b in (note.get("bullets") or []))
        body = f"""---
title: {title}
domain: {DOMAIN}
note_type: dsm_historic_label
tags: [DSM, historic, neurodiversity, diagnostic_criteria]
ni_research_board: false
dsm_historic: true
---

# {title}

_Historic / transitional diagnostic label (era: **{note.get('era')}**). Not the current DSM-5-TR primary code._

## Maps to (current boards)

{maps or '_n/a_'}

## Summary

{note.get('summary') or ''}

## Notes

{bullets or '- _n/a_'}

## Sources

{sources or '- _n/a_'}

## Related living boards

[[Autism]] · [[ADHD]] · [[AuDHD]] · [[Neurodiversity]]
"""
        if dry_run:
            out.append({"ok": True, "dry_run": True, "title": title, "vault_path": rel})
            continue
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        oid = _historic_object_id(slug)
        # Prefer existing registry row for this path
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT object_id FROM intelligence.vault_notes
                        WHERE vault_path = %s LIMIT 1
                        """,
                        (rel,),
                    )
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        oid = int(row[0])
        except Exception as e:
            logger.debug("historic path lookup %s: %s", rel, e)
        try:
            upsert_vault_note(
                domain_key=DOMAIN,
                note_type="entity",
                object_id=oid,
                vault_path=rel,
                title=title,
                note_status="seeded",
                lifecycle="index",
                tags=["DSM", "historic", "neurodiversity"],
                tags_source="ni_structural",
                body_md=body,
                summary_md=f"Historic DSM label: {title}",
                metadata={
                    "dsm_historic": True,
                    "era": note.get("era"),
                    "maps_to": note.get("maps_to") or [],
                },
            )
        except Exception as e:
            logger.warning("historic registry upsert %s: %s", title, e)
        out.append({"ok": True, "title": title, "vault_path": rel, "object_id": oid})
        logger.info("historic DSM note %s → %s", title, rel)
    return out


def _patch_section(body: str, pattern: re.Pattern[str], section_md: str) -> str:
    text = body or ""
    block = "\n" + section_md.strip() + "\n"
    if pattern.search(text):
        return pattern.sub(block, text, count=1)
    # Insert before trailing Notes if present, else append
    m = re.search(r"\n## Notes\n", text)
    if m:
        return text[: m.start()] + block + text[m.start() :]
    return text.rstrip() + "\n" + block


def _list_profiled_papers(limit: int = 40) -> list[dict[str, Any]]:
    from shared.database.connection import get_db_connection_context

    rows: list[dict[str, Any]] = []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.article_id, a.title, a.url, a.published_at, a.summary,
                       p.subjects_studied, p.findings_summary, p.extraction_status
                FROM intelligence.research_paper_profiles p
                JOIN neurodiversity.articles a ON a.id = p.article_id
                WHERE p.domain_key = %s AND p.extraction_status = 'done'
                ORDER BY p.updated_at DESC
                LIMIT %s
                """,
                (DOMAIN, int(limit)),
            )
            for r in cur.fetchall():
                subjects = r[5]
                if isinstance(subjects, str):
                    try:
                        subjects = json.loads(subjects)
                    except json.JSONDecodeError:
                        subjects = []
                findings = r[6]
                if isinstance(findings, str):
                    try:
                        findings = json.loads(findings)
                    except json.JSONDecodeError:
                        findings = findings
                rows.append(
                    {
                        "id": int(r[0]),
                        "title": r[1] or "",
                        "url": r[2] or "",
                        "published": (r[3].isoformat() if r[3] else "")[:10],
                        "summary": r[4] or "",
                        "subjects_studied": subjects if isinstance(subjects, list) else [],
                        "findings_summary": findings,
                        "extraction_status": r[7],
                    }
                )
    return rows


def _match_board_subjects(subjects: list[Any], title: str) -> list[str]:
    blob = " ".join(str(x) for x in subjects) + " " + (title or "")
    blob_l = blob.lower()
    hits: list[str] = []
    for name in SUBJECTS:
        n = name.lower()
        if n == "audhd":
            if ("audhd" in blob_l) or ("adhd" in blob_l and "autism" in blob_l):
                hits.append(name)
            continue
        if n in blob_l or (n == "autism" and "asd" in blob_l):
            hits.append(name)
    return hits or ["Neurodiversity"]


def _finding_summary(article: dict[str, Any]) -> str:
    kf = article.get("findings_summary")
    if isinstance(kf, list) and kf:
        parts = []
        for item in kf[:4]:
            if isinstance(item, dict):
                t = item.get("text") or item.get("finding") or item.get("claim")
                if t:
                    parts.append(str(t).strip())
            elif item:
                parts.append(str(item).strip())
        if parts:
            return "\n\n".join(parts)[:1800]
    if isinstance(kf, str) and kf.strip():
        return kf.strip()[:1800]
    return (article.get("summary") or article.get("title") or "").strip()[:1800]


def _enrich_topic_note(
    title: str,
    entity_id: int,
    *,
    papers: list[dict[str, Any]],
    dry_run: bool,
    skip_wiki: bool = False,
) -> dict[str, Any]:
    from services.research_subject_topics import load_research_subject_topics
    from services.vault_bridge_service import vault_root
    from services.vault_notes_registry_service import upsert_vault_note
    from services.vault_wiki_enrichment_service import (
        build_wiki_section,
        patch_wiki_section,
        retrieve_wiki_hits,
    )
    from shared.vault_note_contract import entity_vault_rel_path

    cfg = load_research_subject_topics().get(DOMAIN) or {}
    keywords = list(cfg.get("keywords") or [])
    subjects = list(cfg.get("subjects") or list(SUBJECTS.keys()))
    rel = entity_vault_rel_path(title, domain_key=DOMAIN, entity_type="subject")
    # Prefer registry path
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vault_path FROM intelligence.vault_notes
                WHERE domain_key=%s AND note_type='entity' AND object_id=%s
                  AND COALESCE(object_id_secondary,0)=0
                LIMIT 1
                """,
                (DOMAIN, int(entity_id)),
            )
            row = cur.fetchone()
            if row and row[0]:
                rel = str(row[0])

    path = vault_root() / rel
    if path.is_file():
        body = path.read_text(encoding="utf-8")
    else:
        tags = " ".join(f"#{k.replace(' ', '_')}" for k in keywords[:12])
        subject_links = ", ".join(f"[[{s}]]" for s in subjects)
        body = f"""---
title: {title}
domain: {DOMAIN}
note_type: research_topic
tags: [{", ".join(repr(k) for k in keywords[:12])}]
ni_research_board: true
---

# {title}

Standing research topic for the News Intelligence **What we know** board.

## Keywords

{tags}

## Related subjects

{subject_links}

## Notes

Accumulating evidence (supported / not supported / open) comes from appraised
papers in the research pathway — not news headlines.
"""

    # Wikipedia (optional — can be slow / preempted on shared Ollama hosts)
    hits: list[dict[str, Any]] = []
    if not skip_wiki:
        hits = retrieve_wiki_hits(
            list(SUBJECTS[title]["wiki_queries"]),
            max_hits=3,
            allow_api_fallback=True,
        )
        # Drop obvious false positives (e.g. "Spectrum" optics for "Autism spectrum")
        hits = [
            h
            for h in hits
            if not (
                title.lower() in ("autism", "audhd")
                and (h.get("title") or "").strip().lower() == "spectrum"
            )
        ]
        wiki_md = build_wiki_section(hits, label=title)
        body = patch_wiki_section(body, wiki_md)

    # Web basics
    body = _patch_section(body, _WEB_SECTION_RE, _build_web_section(title))

    # DSM current + historic definitions
    body = _patch_section(body, _DSM_SECTION_RE, _build_dsm_section(title))

    # Knowledge profile
    kp = _load_knowledge_profile(title)
    body = _patch_section(body, _KP_SECTION_RE, _build_kp_section(kp))

    # Corpus paper links for this board
    linked = []
    for art in papers:
        boards = _match_board_subjects(art.get("subjects_studied") or [], art.get("title") or "")
        if title in boards or (title == "Neurodiversity" and not boards):
            linked.append(art)
    corpus_lines = [
        "## Corpus papers (seeded)",
        "",
        f"_Profiled research papers from ``neurodiversity.articles`` "
        f"({_now_iso()[:19]}Z). Full clippings under ``50_Science/20_Clippings/``._",
        "",
    ]
    if linked:
        for art in linked[:20]:
            corpus_lines.append(f"- [[{art['title']}]] — article:`{art['id']}`")
    else:
        corpus_lines.append("- _No profiled papers matched this board yet._")
    corpus_lines.append("")
    body = _patch_section(body, _CORPUS_SECTION_RE, "\n".join(corpus_lines))

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "vault_path": rel,
            "wiki_hits": len(hits),
            "kp": bool(kp),
            "papers": len(linked),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    # CIFS mounts have occasionally written trailing NULs; never persist them.
    body = body.replace("\x00", "")
    path.write_text(body, encoding="utf-8")
    upsert_vault_note(
        domain_key=DOMAIN,
        note_type="entity",
        object_id=int(entity_id),
        vault_path=rel,
        title=title,
        note_status="seeded",
        lifecycle="living",
        tags=keywords,
        tags_source="ni_structural",
        body_md=body,
        summary_md=f"Research topic board: {title}",
        metadata={
            "research_board": True,
            "keywords": keywords,
            "wiki_enriched_at": _now_iso(),
            "web_basics_at": _now_iso(),
            "dsm_synced_at": _now_iso(),
            "dsm_edition": DSM_CURRENT["edition"],
            "kp_synced_at": _now_iso() if kp else None,
        },
    )
    return {
        "ok": True,
        "vault_path": rel,
        "wiki_hits": len(hits),
        "kp": bool(kp),
        "papers": len(linked),
        "dsm": True,
    }


def _write_paper_clipping(article: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    from services.vault_bridge_service import _render_frontmatter, vault_root
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.vault_note_contract import clipping_vault_rel_path, structural_tags_for_note

    boards = _match_board_subjects(
        article.get("subjects_studied") or [], article.get("title") or ""
    )
    rel = clipping_vault_rel_path(
        published=article.get("published") or "",
        article_id=int(article["id"]),
        title=article.get("title") or "",
        domain_key=DOMAIN,
    )
    summary = _finding_summary(article)
    links = " · ".join(f"[[{b}]]" for b in boards)
    subjects = ", ".join(str(s) for s in (article.get("subjects_studied") or [])[:8])
    day = (article.get("published") or _now_iso()[:10])[:10]
    fm = {
        "ni_domain": DOMAIN,
        "note_type": "clipping",
        "article_id": int(article["id"]),
        "object_id": int(article["id"]),
        "source": article.get("url") or "",
        "status": "processed",
        "created": day,
        "updated": _now_iso()[:10],
        "ni_auto": True,
        "clipping": True,
        "content_kind": "research_paper",
        "tags": structural_tags_for_note(
            note_type="clipping",
            domain_key=DOMAIN,
            extra=["clipping", "research_paper"] + [b.lower() for b in boards],
        ),
    }
    body = f"""# {article.get('title') or f"Article {article['id']}"}

## Summary

{summary.strip() or '_No profile summary yet._'}

## Subjects studied

{subjects or '_n/a_'}

## Related

{links or '_No related wiki notes._'}

## Source

- article:`{article['id']}`
- domain: {DOMAIN}
- content_kind: research_paper
- date: {day}
- url: {article.get('url') or '_none_'}
"""
    md = _render_frontmatter(fm) + body
    if dry_run:
        return {"ok": True, "dry_run": True, "vault_path": rel, "boards": boards}

    path = vault_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    upsert_vault_note(
        domain_key=DOMAIN,
        note_type="clipping",
        object_id=int(article["id"]),
        vault_path=rel,
        title=article.get("title") or f"Article {article['id']}",
        note_status="note_ready",
        lifecycle="seeded",
        last_article_id=int(article["id"]),
        tags=list(fm["tags"]),
        metadata={
            "clipping": True,
            "research_paper": True,
            "article_id": int(article["id"]),
            "source": article.get("url") or "",
            "boards": boards,
        },
        tags_source="ni_structural",
    )
    return {"ok": True, "vault_path": rel, "boards": boards}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-preseed", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--skip-clippings", action="store_true")
    parser.add_argument("--dsm-only", action="store_true", help="Only refresh DSM sections + historic labels")
    parser.add_argument("--paper-limit", type=int, default=30)
    parser.add_argument("--entity-limit", type=int, default=25)
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("NI_VAULT_NOTES_ENABLED", "true")

    stats: dict[str, Any] = {
        "subjects": {},
        "historic_dsm": [],
        "clippings": {"written": 0, "errors": 0},
        "preseed": None,
        "sync": None,
        "dry_run": args.dry_run,
        "vault_root": os.environ.get("NEWS_INTEL_VAULT_PATH"),
        "dsm_edition": DSM_CURRENT["edition"],
    }

    subject_ids = _ensure_subjects()
    papers = [] if args.dsm_only else _list_profiled_papers(limit=args.paper_limit)
    if not args.dsm_only:
        logger.info("profiled papers available: %s", len(papers))
    else:
        # Still need paper list for corpus section when enriching topics
        papers = _list_profiled_papers(limit=args.paper_limit)

    for title, eid in subject_ids.items():
        try:
            res = _enrich_topic_note(
                title,
                eid,
                papers=papers,
                dry_run=args.dry_run,
                skip_wiki=bool(args.dsm_only),
            )
            stats["subjects"][title] = res
            logger.info(
                "topic %s → %s wiki=%s kp=%s papers=%s dsm=%s",
                title,
                res.get("vault_path"),
                res.get("wiki_hits"),
                res.get("kp"),
                res.get("papers"),
                res.get("dsm"),
            )
        except Exception as e:
            logger.exception("enrich %s failed", title)
            stats["subjects"][title] = {"ok": False, "error": str(e)}

    try:
        stats["historic_dsm"] = _write_historic_dsm_notes(dry_run=args.dry_run)
    except Exception as e:
        logger.exception("historic DSM notes failed")
        stats["historic_dsm"] = [{"ok": False, "error": str(e)}]

    if not args.skip_clippings and not args.dsm_only:
        for art in papers:
            try:
                res = _write_paper_clipping(art, dry_run=args.dry_run)
                if res.get("ok"):
                    stats["clippings"]["written"] += 1
                    logger.info(
                        "clipping %s → %s %s",
                        art["id"],
                        res.get("vault_path"),
                        res.get("boards"),
                    )
                else:
                    stats["clippings"]["errors"] += 1
            except Exception as e:
                logger.warning("clipping %s failed: %s", art.get("id"), e)
                stats["clippings"]["errors"] += 1

    if not args.skip_preseed and not args.dry_run and not args.dsm_only:
        try:
            from services.vault_notes_preseed_service import preseed_vault_notes

            stats["preseed"] = preseed_vault_notes(
                domain_key=DOMAIN,
                entity_limit=args.entity_limit,
                storyline_limit=0,
                force=False,
                dry_run=False,
            )
        except Exception as e:
            logger.warning("preseed failed: %s", e)
            stats["preseed"] = {"ok": False, "error": str(e)}

    if not args.skip_sync and not args.dry_run:
        try:
            from services.vault_tag_link_sync_service import sync_vault_tags_and_links

            sync_kwargs: dict[str, Any] = {"limit": 400}
            if args.dsm_only:
                sync_kwargs["roots"] = ("50_Science",)
                sync_kwargs["limit"] = 200
            stats["sync"] = sync_vault_tags_and_links(**sync_kwargs)
        except Exception as e:
            logger.warning("tag/link sync failed: %s", e)
            stats["sync"] = {"ok": False, "error": str(e)}

    print(json.dumps(stats, indent=2, default=str))
    ok_topics = sum(1 for v in stats["subjects"].values() if v.get("ok"))
    return 0 if ok_topics >= 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
