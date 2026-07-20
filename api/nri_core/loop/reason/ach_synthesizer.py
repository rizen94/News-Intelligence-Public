"""ACH-contract LLM reasoner with causal-language linter."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from nri_core.llm.ollama_client import chat_json

CAUSAL_TERMS = re.compile(
    r"\b(caused|bought|in exchange for|led to|resulted in|because of)\b",
    re.I,
)

ACH_SCHEMA = {
    "mundane_explanation": "string — required first",
    "competing_hypotheses": "list of strings",
    "cheapest_test": "string",
    "confidence": "float 0-1",
    "causal_claims": "list — must be empty unless mundane + temporal order present",
}


@dataclass
class ACHResult:
    mundane_explanation: str
    competing_hypotheses: list[str]
    cheapest_test: str
    confidence: float
    causal_flags: list[str]
    raw: dict[str, Any]


def lint_causal_language(text: str) -> list[str]:
    return [m.group(0) for m in CAUSAL_TERMS.finditer(text)]


def causal_claims_allowed(
    claims: list[Any],
    *,
    typed_edge_ids: list[int] | None = None,
    evidence_context_ids: list[int] | None = None,
) -> tuple[list[Any], list[str]]:
    """
    ACH linter: causal_claims may only survive when edge+evidence present (Phase A).
    Returns (allowed_claims, rejection_flags).
    """
    edges = typed_edge_ids or []
    evidence = evidence_context_ids or []
    if edges and evidence:
        return list(claims or []), []
    flags: list[str] = []
    if claims:
        flags.append("causal_claims_stripped_missing_edge_or_evidence")
    return [], flags


def build_reasoner_prompt(candidate: dict[str, Any], dossier: dict[str, Any]) -> str:
    edge_ids = dossier.get("typed_edge_ids") or candidate.get("typed_edge_ids") or []
    evidence_ids = dossier.get("evidence_context_ids") or candidate.get("evidence_context_ids") or []
    return f"""You are an ACH analyst. Output JSON only.

UNTRUSTED_EVIDENCE_START
{candidate}
{dossier}
UNTRUSTED_EVIDENCE_END

Rules:
1. State mundane_explanation FIRST.
2. List competing_hypotheses including mundane one.
3. Propose cheapest_test to disconfirm.
4. Do NOT use causal language unless temporal order is explicit.
5. causal_claims must be empty unless typed causal edge ids {edge_ids} AND evidence_context_ids {evidence_ids} are both non-empty.
6. confidence is epistemic uncertainty, not guilt.

Return JSON keys: mundane_explanation, competing_hypotheses, cheapest_test, confidence, causal_claims (list).
"""


def reason_candidate(candidate: dict[str, Any], dossier: dict[str, Any]) -> ACHResult:
    prompt = build_reasoner_prompt(candidate, dossier)
    raw = chat_json(prompt=prompt, role="reasoner")
    mundane = str(raw.get("mundane_explanation", ""))
    flags = lint_causal_language(mundane)
    for hyp in raw.get("competing_hypotheses", []):
        flags.extend(lint_causal_language(str(hyp)))
    allowed, claim_flags = causal_claims_allowed(
        list(raw.get("causal_claims") or []),
        typed_edge_ids=list(dossier.get("typed_edge_ids") or candidate.get("typed_edge_ids") or []),
        evidence_context_ids=list(
            dossier.get("evidence_context_ids") or candidate.get("evidence_context_ids") or []
        ),
    )
    flags.extend(claim_flags)
    raw = dict(raw)
    raw["causal_claims"] = allowed
    return ACHResult(
        mundane_explanation=mundane,
        competing_hypotheses=list(raw.get("competing_hypotheses", [])),
        cheapest_test=str(raw.get("cheapest_test", "")),
        confidence=float(raw.get("confidence", 0.3)),
        causal_flags=flags,
        raw=raw,
    )
