"""
Curated research subject boards + vault keywords for the /research topic index.

Config: api/config/research_subject_topics.yaml
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "research_subject_topics.yaml"
)

# Fallback if YAML missing
_DEFAULT: dict[str, dict[str, Any]] = {
    "neurodiversity": {
        "label": "Neurodiversity",
        "subjects": ["Autism", "ADHD", "AuDHD", "Neurodiversity"],
        "keywords": [
            "Autism",
            "ASD",
            "ADHD",
            "AuDHD",
            "neurodiversity",
            "genetics",
            "intervention",
            "clinical trials",
        ],
    },
    "artificial-intelligence": {
        "label": "Artificial intelligence",
        "subjects": [
            "Artificial Intelligence",
            "Large Language Models",
            "Computer Vision",
            "AI Alignment",
            "Robotics",
        ],
        "keywords": [
            "LLMs",
            "agents",
            "alignment",
            "computer vision",
            "VLMs",
            "reinforcement learning",
            "robotics",
            "machine learning",
        ],
    },
    "medicine": {
        "label": "Medicine",
        "subjects": [
            "Clinical Trials",
            "Epidemiology",
            "Oncology",
            "Infectious Disease",
            "Public Health",
            "Genomics",
        ],
        "keywords": [
            "clinical trials",
            "epidemiology",
            "oncology",
            "infectious disease",
            "public health",
            "genomics",
        ],
    },
}


@lru_cache(maxsize=1)
def load_research_subject_topics() -> dict[str, dict[str, Any]]:
    try:
        import yaml

        raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and raw:
            out: dict[str, dict[str, Any]] = {}
            for dk, block in raw.items():
                if not isinstance(block, dict):
                    continue
                out[str(dk)] = {
                    "label": str(block.get("label") or dk),
                    "subjects": [
                        str(x).strip()
                        for x in (block.get("subjects") or [])
                        if str(x).strip()
                    ],
                    "keywords": [
                        str(x).strip()
                        for x in (block.get("keywords") or [])
                        if str(x).strip()
                    ],
                }
            if out:
                return out
    except Exception as e:
        logger.debug("research_subject_topics load failed: %s", e)
    return {k: dict(v) for k, v in _DEFAULT.items()}


def domain_fallback_subjects() -> dict[str, list[str]]:
    cfg = load_research_subject_topics()
    return {dk: list(block.get("subjects") or []) for dk, block in cfg.items()}


def domain_keywords(domain_key: str) -> list[str]:
    cfg = load_research_subject_topics()
    block = cfg.get((domain_key or "").strip()) or {}
    return list(block.get("keywords") or [])


def domain_label(domain_key: str) -> str:
    cfg = load_research_subject_topics()
    block = cfg.get((domain_key or "").strip()) or {}
    return str(block.get("label") or domain_key)


def list_domain_topic_index() -> list[dict[str, Any]]:
    """Ordered domain blocks for the Research index (label + keywords)."""
    cfg = load_research_subject_topics()
    order = ["neurodiversity", "artificial-intelligence", "medicine"]
    out: list[dict[str, Any]] = []
    for dk in order:
        if dk not in cfg:
            continue
        block = cfg[dk]
        out.append(
            {
                "domain_key": dk,
                "label": block.get("label") or dk,
                "keywords": list(block.get("keywords") or []),
                "subjects": list(block.get("subjects") or []),
            }
        )
    for dk, block in cfg.items():
        if dk in order:
            continue
        out.append(
            {
                "domain_key": dk,
                "label": block.get("label") or dk,
                "keywords": list(block.get("keywords") or []),
                "subjects": list(block.get("subjects") or []),
            }
        )
    return out
